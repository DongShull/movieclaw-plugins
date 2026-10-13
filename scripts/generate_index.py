#!/usr/bin/env python3
"""Build ``index.json`` (schema 1) from plugin manifests, ``store.json``, and releases.

A plugin appears only after it has at least one published version. Metadata
(title, permissions, sdk, store fields) comes from the git tree. Download URLs
and hashes come from ``--previous`` (the catalog already online) overlaid with
``--release`` / ``--releases``.

    python3 scripts/generate_index.py --generated-at 2026-10-13T00:00:00Z --output index.json
    python3 scripts/generate_index.py --check index.json
    python3 scripts/generate_index.py \\
        --previous dist/prev/index.json \\
        --release hello-note 0.1.0 <sha256> <size> 2026-10-13T00:00:00Z \\
        --sign --output dist/index.json --sig dist/index.json.sig
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path

from pluginlib import (
    REPO,
    SHA256_RE,
    VERSION_RE,
    PluginError,
    asset_url,
    load_store,
    permissions_of,
    plugin_table,
    public_url,
    version_sort_key,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "index.schema.json"
GENERATED_AT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def _dumps(document: dict) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def _platforms(table: dict) -> list[str]:
    if table["runtime"] == "exec":
        platforms = list(table.get("platforms") or [])
        if not platforms:
            raise PluginError(f"{table['id']} 是 exec，清单里必须有 platforms")
        return [str(item) for item in platforms]
    return ["any"]


def _artifact_platform(table: dict, record: dict) -> str:
    if record.get("platform"):
        return str(record["platform"])
    if table["runtime"] != "exec":
        return "any"
    platforms = _platforms(table)
    if len(platforms) == 1:
        return platforms[0]
    raise PluginError(f"{table['id']} 声明了多个 platforms，这条发布记录必须带 platform")


def _plugin_document(directory: Path, repo: str, versions: list[dict]) -> dict:
    table = plugin_table(directory)
    store = load_store(directory)
    versions = sorted(versions, key=lambda item: version_sort_key(item["version"]), reverse=True)
    stables = [item for item in versions if "-" not in item["version"].split("+", 1)[0]]
    latest = (stables or versions)[0]["version"] if versions else None
    description = table["description"] or store.get("summary") or ""
    return {
        "id": table["id"],
        "name": table["title"],
        "description": description,
        "author": store["author"],
        "homepage": store["homepage"],
        "license": store["license"],
        "origin": store["origin"],
        "icon": public_url(repo, store.get("icon")),
        "screenshots": [
            url
            for item in store.get("screenshots") or []
            if (url := public_url(repo, item))
        ],
        "runtime": table["runtime"],
        "sdk": table["sdk"],
        "app": store.get("app"),
        "permissions": permissions_of(directory),
        "platforms": _platforms(table),
        "latest": latest,
        "versions": versions,
    }


def _blank_version(plugin_id: str, version: str, repo: str, store: dict) -> dict:
    return {
        "version": version,
        "released_at": None,
        "changelog_url": f"https://github.com/{repo}/releases/tag/{plugin_id}-v{version}",
        "min_app": store.get("min_app"),
        "max_app": store.get("max_app"),
        "artifacts": [],
    }


def _apply_release(
    versions: dict[str, dict],
    directory: Path,
    repo: str,
    record: dict,
) -> None:
    table = plugin_table(directory)
    plugin_id = table["id"]
    version = str(record["version"])
    if not VERSION_RE.fullmatch(version):
        raise PluginError(f"{plugin_id} 的发布版本 {version!r} 不合法")
    sha = str(record["sha256"])
    if not SHA256_RE.fullmatch(sha):
        raise PluginError(f"{plugin_id} {version} 的 sha256 须是 64 位小写十六进制")
    size = record["size"]
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise PluginError(f"{plugin_id} {version} 的 size 须是非负整数")
    released_at = str(record["released_at"])
    if not GENERATED_AT_RE.fullmatch(released_at):
        raise PluginError(f"{plugin_id} {version} 的 released_at 须是 UTC，如 2026-10-13T00:00:00Z")
    store = load_store(directory)
    current = versions.get(version) or _blank_version(plugin_id, version, repo, store)
    current["released_at"] = released_at
    current["min_app"] = record.get("min_app", store.get("min_app"))
    current["max_app"] = record.get("max_app", store.get("max_app"))
    filename = str(record.get("filename") or f"{plugin_id}-{version}.mcplugin")
    platform = _artifact_platform(table, record)
    artifact = {
        "platform": platform,
        "filename": filename,
        "url": asset_url(repo, plugin_id, version, filename),
        "sha256": sha,
        "size": size,
    }
    others = [item for item in current["artifacts"] if item.get("platform") != platform]
    current["artifacts"] = sorted([*others, artifact], key=lambda item: item["platform"])
    versions[version] = current


def _normalize_version(plugin_id: str, item: dict, repo: str) -> dict:
    version = str(item["version"])
    artifacts = []
    for art in item.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        filename = str(art.get("filename") or f"{plugin_id}-{version}.mcplugin")
        artifacts.append(
            {
                "platform": str(art.get("platform") or "any"),
                "filename": filename,
                "url": str(art.get("url") or asset_url(repo, plugin_id, version, filename)),
                "sha256": str(art.get("sha256") or ""),
                "size": int(art.get("size") or 0),
            }
        )
    released_at = item.get("released_at")
    return {
        "version": version,
        "released_at": released_at if isinstance(released_at, str) else "",
        "changelog_url": str(
            item.get("changelog_url")
            or f"https://github.com/{repo}/releases/tag/{plugin_id}-v{version}"
        ),
        "min_app": item.get("min_app") if isinstance(item.get("min_app"), str) else None,
        "max_app": item.get("max_app") if isinstance(item.get("max_app"), str) else None,
        "artifacts": artifacts,
    }


def _versions_from_previous(previous: dict, plugin_id: str, repo: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for plugin in previous.get("plugins") or []:
        if not isinstance(plugin, dict) or plugin.get("id") != plugin_id:
            continue
        for item in plugin.get("versions") or []:
            if isinstance(item, dict) and isinstance(item.get("version"), str):
                found[item["version"]] = _normalize_version(plugin_id, item, repo)
    return found


def build_index(
    *,
    plugins_dir: Path,
    repo: str,
    generated_at: str,
    previous: dict | None,
    releases: list[dict],
    signed: bool,
    key_id: str | None,
) -> dict:
    if not GENERATED_AT_RE.fullmatch(generated_at):
        raise PluginError("generated_at 须是 UTC，如 2026-10-13T00:00:00Z")
    if signed and not key_id:
        raise PluginError("签名索引必须带 key_id")
    if not signed and key_id is not None:
        raise PluginError("未签名索引的 key_id 须是 null")
    by_id: dict[str, list[dict]] = {}
    for record in releases:
        plugin_id = str(record["id"])
        by_id.setdefault(plugin_id, []).append(record)

    plugins: list[dict] = []
    manifests = sorted(plugins_dir.glob("*/movieclaw-plugin.toml")) if plugins_dir.is_dir() else []
    known = {path.parent.name for path in manifests}
    missing = sorted(set(by_id) - known)
    if missing:
        names = "、".join(missing)
        raise PluginError(f"发布记录里的插件在 {plugins_dir} 中不存在：{names}")
    for manifest in manifests:
        directory = manifest.parent
        table = plugin_table(directory)
        plugin_id = table["id"]
        if directory.name != plugin_id:
            raise PluginError(f"{directory} 的目录名须与清单 id {plugin_id} 一致")
        versions = _versions_from_previous(previous or {}, plugin_id, repo)
        for record in by_id.get(plugin_id, []):
            _apply_release(versions, directory, repo, record)
        if not versions:
            continue
        plugins.append(_plugin_document(directory, repo, list(versions.values())))
    plugins.sort(key=lambda item: item["id"])
    return {
        "schema": 1,
        "generated_at": generated_at,
        "signed": signed,
        "key_id": key_id,
        "plugins": plugins,
    }


def check_index(path: Path, schema_path: Path = SCHEMA_PATH) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise PluginError("校验索引需要 jsonschema：pip install jsonschema") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if schema.get("properties", {}).get("schema", {}).get("const") != 1:
        raise PluginError(f"{schema_path} 不是 schema v1")
    document = json.loads(path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.Draft202012Validator.FORMAT_CHECKER
    )
    errors = sorted(validator.iter_errors(document), key=lambda err: list(err.path))
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise PluginError(f"{path} 不符合 {schema_path.name}：{where}：{first.message}")


def sign_bytes(raw: bytes, pem: str) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(pem.encode(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise PluginError("RELEASE_SIGNING_KEY 须是 Ed25519 私钥 PEM")
    return base64.b64encode(key.sign(raw)) + b"\n"


def _load_previous(path: Path | None) -> dict | None:
    if path is None:
        return None
    if not path.is_file():
        raise PluginError(f"找不到已有索引 {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise PluginError(f"{path} 不是 JSON 对象")
    return data


def _load_releases(path: Path | None, inline: list[list[str]]) -> list[dict]:
    records: list[dict] = []
    if path is not None:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("releases", data)
        if not isinstance(data, list):
            raise PluginError("--releases 须是数组，或 {releases: [...]}")
        for item in data:
            if not isinstance(item, dict):
                raise PluginError("--releases 的每一项须是对象")
            records.append(item)
    for item in inline:
        plugin_id, version, sha, size, released_at = item
        records.append(
            {
                "id": plugin_id,
                "version": version,
                "sha256": sha,
                "size": int(size),
                "released_at": released_at,
            }
        )
    return records


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Generate or check the plugin catalog index.")
    parser.add_argument("--plugins", type=Path, default=ROOT / "plugins")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", REPO))
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--previous", type=Path, default=None)
    parser.add_argument("--releases", type=Path, default=None)
    parser.add_argument(
        "--release",
        action="append",
        nargs=5,
        metavar=("ID", "VERSION", "SHA256", "SIZE", "RELEASED_AT"),
        default=[],
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--sign", action="store_true")
    parser.add_argument(
        "--key-id",
        default=os.environ.get("RELEASE_SIGNING_KEY_ID") or "catalog-1",
    )
    parser.add_argument("--sig", type=Path, default=None)
    parser.add_argument("--check", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        if args.check is not None:
            check_index(args.check)
            print(f"ok {args.check}")
            return 0
        if args.generated_at is None:
            raise PluginError("请传 --generated-at（UTC，如 2026-10-13T00:00:00Z）")
        signed = bool(args.sign)
        key_id = args.key_id if signed else None
        document = build_index(
            plugins_dir=args.plugins,
            repo=args.repo,
            generated_at=args.generated_at,
            previous=_load_previous(args.previous),
            releases=_load_releases(args.releases, args.release),
            signed=signed,
            key_id=key_id,
        )
        text = _dumps(document)
        raw = text.encode("utf-8")
        if args.output is None:
            sys.stdout.buffer.write(raw)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(raw)
            print(f"wrote {args.output}", file=sys.stderr)
        if signed:
            pem = os.environ.get("RELEASE_SIGNING_KEY", "")
            if not pem.strip():
                raise PluginError("签了名却没有环境变量 RELEASE_SIGNING_KEY")
            signature = sign_bytes(raw, pem)
            sig_path = args.sig
            if sig_path is None:
                if args.output is None:
                    raise PluginError("签名请同时给出 --output 与 --sig")
                sig_path = args.output.with_name(args.output.name + ".sig")
            sig_path.write_bytes(signature)
            print(f"wrote {sig_path}", file=sys.stderr)
        if args.output is not None and SCHEMA_PATH.is_file():
            check_index(args.output)
    except PluginError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: JSON：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
