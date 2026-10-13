#!/usr/bin/env python3
"""Choose which plugin directories a pull request must validate.

Relevant changes are ``plugins/<id>/``, ``example/``, ``scripts/``,
``index.schema.json``, and this repo's CI workflow. The example plugin is
always included when anything relevant changed. Script or schema changes
validate every plugin that is already in ``plugins/`` plus the example.

Reads ``BASE_SHA`` and writes ``run`` and ``dirs`` to ``$GITHUB_OUTPUT``
when that variable is set. ``dirs`` is a space-separated list.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = "example/hello-note"


def select(changed: list[str], root: Path = ROOT) -> tuple[bool, list[str]]:
    force_all = False
    plugin_ids: list[str] = []
    saw_relevant = False
    for path in changed:
        if (
            path.startswith("scripts/")
            or path == ".github/workflows/ci.yml"
            or path == "index.schema.json"
        ):
            force_all = True
            saw_relevant = True
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "plugins":
            plugin_ids.append(parts[1])
            saw_relevant = True
        if parts and parts[0] == "example":
            saw_relevant = True
    if not saw_relevant:
        return False, []
    dirs: list[str] = []
    if force_all:
        plugins = root / "plugins"
        if plugins.is_dir():
            for manifest in sorted(plugins.glob("*/movieclaw-plugin.toml")):
                dirs.append(manifest.parent.relative_to(root).as_posix())
    else:
        for plugin_id in sorted(set(plugin_ids)):
            manifest = root / "plugins" / plugin_id / "movieclaw-plugin.toml"
            if manifest.is_file():
                dirs.append(f"plugins/{plugin_id}")
    example = root / EXAMPLE / "movieclaw-plugin.toml"
    if example.is_file() and EXAMPLE not in dirs:
        dirs.append(EXAMPLE)
    return True, dirs


def changed_files(base: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in proc.stdout.splitlines() if line]


def emit(key: str, value: str) -> None:
    print(f"{key}={value}")
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{key}={value}\n")


def main() -> int:
    base = os.environ.get("BASE_SHA", "")
    if not base:
        print("error: BASE_SHA is required", file=sys.stderr)
        return 1
    run, dirs = select(changed_files(base))
    emit("run", "true" if run else "false")
    emit("dirs", " ".join(dirs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
