# qBittorrent 下载器（参考副本）

这是从 [MovieClaw](https://github.com/movieclaw/MovieClaw) 复制过来的参考源码，不是本仓库要发布的插件。

- 上游路径：`src/movieclaw_plugins/qbittorrent`
- 上游提交：`779712c4d8d2c2c320021ab0e31cde95821dd493`
- 权威副本在 MovieClaw 仓库，并随应用一起打包。要改行为，改上游；这里只供对照。
- 运行方式：`runtime = "process"`
- 不要放进 `plugins/`，不会进索引，也不要打 Release。
- 重新同步：`python3 scripts/sync_examples.py 779712c4d8d2c2c320021ab0e31cde95821dd493`

## 注意

下载器依赖宿主已经提供的协议库，不放进插件自己的 `vendor/`：qBittorrent 用 `qbittorrent-api`（import 名 `qbittorrentapi`），Transmission 用 `transmission-rpc`（import 名 `transmission_rpc`）。协议库不在运行环境里时，入口模块导入会失败。

清单是 `runtime = process`。随应用携带时，宿主把它当内置插件装进主进程；同 id 的插件包装上后会顶掉这一份，卸掉之后随应用的版本回来。

## 测试

插件目录里没有 `tests/`。用例在 MovieClaw 的 `tests/downloader/unit/test_qbittorrent.py` 和 `tests/downloader/test_state_normalize.py`，从 `movieclaw_plugins.qbittorrent` 导入，并依赖 `movieclaw_downloader` 和 `qbittorrentapi`，已省略。

