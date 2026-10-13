"""sync_examples copies a MovieClaw tree without modifying it."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import sync_examples

MARKED = """# 标题

前文。

<!-- sync-examples:begin -->
占位
<!-- sync-examples:end -->

后文。
"""


def manifest(plugin_id: str, title: str, *, runtime: str = "process", entry: str = "entry_mod") -> str:
    return (
        "[plugin]\n"
        f'id = "{plugin_id}"\n'
        f'title = "{title}"\n'
        'version = "1.0.0"\n'
        f'entry = "{entry}"\n'
        f'runtime = "{runtime}"\n'
        'sdk = "^1.0"\n'
        "\n"
        "[permissions]\n"
        "operations = []\n"
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(path: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "-A")
    git(
        path,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=Test",
        "commit",
        "-q",
        "-m",
        message,
    )
    return git(path, "rev-parse", "HEAD").stdout.strip()


def make_upstream(path: Path) -> None:
    write(path / "plugins" / "watch-presence" / "movieclaw-plugin.toml", manifest(
        "watch-presence", "服务器观看动态", runtime="inline", entry="watch_presence"
    ))
    write(path / "plugins" / "watch-presence" / "watch_presence.py", "SENTINEL_WATCH = 1\n")
    write(path / "plugins" / "watch-presence" / "README.md", "# 上游说明\n\n安装步骤。\n")
    write(
        path / "plugins" / "watch-presence" / "tests" / "test_policy.py",
        "import pytest\n\ndef test_policy():\n    assert True\n",
    )
    write(
        path / "src" / "movieclaw_plugins" / "weixin" / "movieclaw-plugin.toml",
        manifest("weixin-channel", "微信通道", entry="weixin_channel"),
    )
    write(path / "src" / "movieclaw_plugins" / "weixin" / "__init__.py", '"""weixin package"""\n')
    write(
        path / "src" / "movieclaw_plugins" / "weixin" / "weixin_channel" / "__init__.py",
        "ENTRY = 'weixin'\n",
    )
    write(
        path / "src" / "movieclaw_plugins" / "qbittorrent" / "movieclaw-plugin.toml",
        manifest("qbittorrent-downloader", "qBittorrent 下载器", entry="qbittorrent_downloader"),
    )
    write(
        path / "src" / "movieclaw_plugins" / "qbittorrent" / "qbittorrent_downloader" / "client.py",
        "import qbittorrentapi\n",
    )
    write(
        path / "src" / "movieclaw_plugins" / "plain" / "movieclaw-plugin.toml",
        manifest("plain-note", "独立测试", entry="plain_note"),
    )
    write(path / "src" / "movieclaw_plugins" / "plain" / "plain_note.py", "VALUE = 1\n")
    write(path / "src" / "movieclaw_plugins" / "plain" / "tests" / "__init__.py", "")
    write(
        path / "src" / "movieclaw_plugins" / "plain" / "tests" / "test_plain.py",
        "import unittest\n\n"
        "class PlainTest(unittest.TestCase):\n"
        "    def test_value(self):\n"
        "        self.assertEqual(1, 1)\n",
    )
    write(
        path / "src" / "movieclaw_plugins" / "broken" / "movieclaw-plugin.toml",
        manifest("broken-note", "跑不通", entry="broken_note"),
    )
    write(path / "src" / "movieclaw_plugins" / "broken" / "broken_note.py", "VALUE = 0\n")
    write(path / "src" / "movieclaw_plugins" / "broken" / "tests" / "__init__.py", "")
    write(
        path / "src" / "movieclaw_plugins" / "broken" / "tests" / "test_bad.py",
        "import unittest\n\n"
        "class BadTest(unittest.TestCase):\n"
        "    def test_bad(self):\n"
        "        self.fail('nope')\n",
    )


def make_dest(path: Path) -> None:
    write(path / "README.md", MARKED)
    write(path / "example" / "GUIDE.md", MARKED)
    write(path / "example" / "hello-note" / "keep.txt", "keep\n")
    write(path / "example" / "stale-plugin" / "movieclaw-plugin.toml", "old\n")
    write(
        path / "example" / "UPSTREAM.json",
        json.dumps(
            {
                "repo": "https://github.com/movieclaw/MovieClaw",
                "commit": "a" * 40,
                "plugins": [{"id": "stale-plugin"}, {"id": "hello-note"}],
            }
        ),
    )


class SyncExamplesTest(unittest.TestCase):
    def test_copies_sources_keeps_upstream_clean_and_updates_sha(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "MovieClaw"
            dest = root / "plugins-repo"
            upstream.mkdir()
            make_upstream(upstream)
            git(upstream, "init", "-q")
            sha = commit_all(upstream, "init")
            make_dest(dest)
            before = git(upstream, "status", "--porcelain").stdout

            with contextlib.redirect_stdout(io.StringIO()):
                code = sync_examples.main(["--source", str(upstream), "--repo-root", str(dest)])

            self.assertEqual(code, 0)
            self.assertEqual(git(upstream, "status", "--porcelain").stdout, before)
            self.assertEqual(
                (upstream / "plugins" / "watch-presence" / "watch_presence.py").read_text(encoding="utf-8"),
                "SENTINEL_WATCH = 1\n",
            )
            copied = dest / "example" / "watch-presence" / "watch_presence.py"
            self.assertEqual(copied.read_text(encoding="utf-8"), "SENTINEL_WATCH = 1\n")
            self.assertFalse((dest / "example" / "watch-presence" / "tests").exists())
            self.assertEqual(
                (dest / "example" / "watch-presence" / "README.upstream.md").read_text(encoding="utf-8"),
                "# 上游说明\n\n安装步骤。\n",
            )
            readme = (dest / "example" / "watch-presence" / "README.md").read_text(encoding="utf-8")
            self.assertIn("plugins/watch-presence", readme)
            self.assertIn(sha, readme)
            self.assertIn('runtime = "inline"', readme)
            self.assertIn("movieclaw_api", readme)
            self.assertIn("movieclaw_kernel", readme)
            self.assertIn("已省略", readme)

            weixin = (dest / "example" / "weixin-channel" / "weixin_channel" / "__init__.py").read_text(
                encoding="utf-8"
            )
            self.assertEqual(weixin, "ENTRY = 'weixin'\n")
            weixin_readme = (dest / "example" / "weixin-channel" / "README.md").read_text(encoding="utf-8")
            self.assertIn("src/movieclaw_plugins/weixin", weixin_readme)
            self.assertIn(sha, weixin_readme)
            self.assertIn('runtime = "process"', weixin_readme)

            qbt = (dest / "example" / "qbittorrent-downloader" / "README.md").read_text(encoding="utf-8")
            self.assertIn("qbittorrent-api", qbt)
            self.assertIn("transmission-rpc", qbt)
            self.assertFalse((dest / "example" / "qbittorrent-downloader" / "tests").exists())

            self.assertTrue((dest / "example" / "plain-note" / "tests" / "test_plain.py").is_file())
            plain_readme = (dest / "example" / "plain-note" / "README.md").read_text(encoding="utf-8")
            self.assertIn("已原样复制", plain_readme)
            self.assertFalse((dest / "example" / "broken-note" / "tests").exists())
            self.assertIn("已省略", (dest / "example" / "broken-note" / "README.md").read_text(encoding="utf-8"))

            self.assertEqual((dest / "example" / "hello-note" / "keep.txt").read_text(encoding="utf-8"), "keep\n")
            self.assertFalse((dest / "example" / "stale-plugin").exists())

            record = json.loads((dest / "example" / "UPSTREAM.json").read_text(encoding="utf-8"))
            self.assertEqual(record["commit"], sha)
            ids = [item["id"] for item in record["plugins"]]
            self.assertEqual(
                ids,
                ["watch-presence", "weixin-channel", "qbittorrent-downloader", "broken-note", "plain-note"],
            )
            self.assertFalse(record["plugins"][0]["tests_included"])
            plain = next(item for item in record["plugins"] if item["id"] == "plain-note")
            self.assertTrue(plain["tests_included"])

            guide = (dest / "example" / "GUIDE.md").read_text(encoding="utf-8")
            readme_root = (dest / "README.md").read_text(encoding="utf-8")
            self.assertIn(sha, guide)
            self.assertIn(sha, readme_root)
            self.assertIn("前文。", guide)
            self.assertIn("后文。", guide)
            self.assertIn("](watch-presence/)", guide)
            self.assertIn("](example/watch-presence/)", readme_root)
            self.assertNotIn("占位", guide)

            write(
                upstream / "src" / "movieclaw_plugins" / "weixin" / "weixin_channel" / "__init__.py",
                "ENTRY = 'updated'\n",
            )
            sha2 = commit_all(upstream, "update weixin")
            with contextlib.redirect_stdout(io.StringIO()):
                sync_examples.main(["--source", str(upstream), "--repo-root", str(dest)])
            record2 = json.loads((dest / "example" / "UPSTREAM.json").read_text(encoding="utf-8"))
            self.assertEqual(record2["commit"], sha2)
            self.assertNotEqual(sha2, sha)
            updated = (dest / "example" / "weixin-channel" / "weixin_channel" / "__init__.py").read_text(
                encoding="utf-8"
            )
            self.assertEqual(updated, "ENTRY = 'updated'\n")
            self.assertIn(sha2, (dest / "example" / "weixin-channel" / "README.md").read_text(encoding="utf-8"))
            self.assertEqual(git(upstream, "status", "--porcelain").stdout, "")

    def test_refuses_a_dirty_movieclaw_checkout(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "MovieClaw"
            dest = root / "plugins-repo"
            upstream.mkdir()
            make_upstream(upstream)
            git(upstream, "init", "-q")
            commit_all(upstream, "init")
            write(upstream / "plugins" / "watch-presence" / "extra.py", "x = 1\n")
            make_dest(dest)
            with self.assertRaises(SystemExit):
                sync_examples.main(["--source", str(upstream), "--repo-root", str(dest)])
            self.assertFalse((dest / "example" / "watch-presence").exists())
            self.assertTrue((upstream / "plugins" / "watch-presence" / "extra.py").is_file())


if __name__ == "__main__":
    unittest.main()
