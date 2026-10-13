# 服务器观看动态（参考副本）

这是从 [MovieClaw](https://github.com/movieclaw/MovieClaw) 复制过来的参考源码，不是本仓库要发布的插件。

- 上游路径：`plugins/watch-presence`
- 上游提交：`779712c4d8d2c2c320021ab0e31cde95821dd493`
- 权威副本在 MovieClaw 仓库，并随应用一起打包。要改行为，改上游；这里只供对照。
- 运行方式：`runtime = "inline"`
- 不要放进 `plugins/`，不会进索引，也不要打 Release。
- 重新同步：`python3 scripts/sync_examples.py 779712c4d8d2c2c320021ab0e31cde95821dd493`

## 注意

这份插件是 `runtime = inline`，在主进程里导入，和主程序同一套权限。它直接 import 宿主内部模块 `movieclaw_api`、`movieclaw_db`、`movieclaw_playback`、`movieclaw_kernel`，不是只依赖 SDK 的写法。第三方插件不要照这个依赖面抄。目录里的 `settings.html` 宿主不加载。

上游目录自带的 `README.md` 原样另存为 `README.upstream.md`。

## 测试

上游目录里有 `tests/test_policy.py` 和 `tests/test_presence.py`，都不能单独跑，已省略。`test_presence.py` 要装进真实 MovieClaw 进程，用 pytest，还要数据库和登录会话。`test_policy.py` 也用 pytest；一旦导入 `watch_presence`，就会加载宿主内部的 `movieclaw_api`、`movieclaw_db`、`movieclaw_playback`、`movieclaw_kernel`。

