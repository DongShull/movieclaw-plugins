# 网盘规格预探（参考副本）

这是从 [MovieClaw](https://github.com/movieclaw/MovieClaw) 复制过来的参考源码，不是本仓库要发布的插件。

- 上游路径：`src/movieclaw_plugins/strm_prefetch`
- 上游提交：`779712c4d8d2c2c320021ab0e31cde95821dd493`
- 权威副本在 MovieClaw 仓库，并随应用一起打包。要改行为，改上游；这里只供对照。
- 运行方式：`runtime = "process"`
- 不要放进 `plugins/`，不会进索引，也不要打 Release。
- 重新同步：`python3 scripts/sync_examples.py 779712c4d8d2c2c320021ab0e31cde95821dd493`

## 注意

清单是 `runtime = process`。随应用携带时，宿主把它当内置插件装进主进程；同 id 的插件包装上后会顶掉这一份，卸掉之后随应用的版本回来。

## 测试

插件目录里没有 `tests/`。用例在 MovieClaw 的 `tests/api/test_strm_prefetch_plugin.py`，要起真实应用并打桩探测，不能对着 `example/strm-prefetch` 单独跑，已省略。

