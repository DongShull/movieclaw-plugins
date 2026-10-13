"""入库笔记：整理入库完成后，按设置记下片名。

这是 ``runtime = "process"`` 的最小示例。判断放在模块顶层的纯函数里，测试不启动宿主。
``apply`` 只做登记：一个带稳定 id 的可靠订阅，外加插件数据里的两个键。
"""

from pydantic import BaseModel, Field

from movieclaw_api.plugins.keys import PLUGIN_DATA
from movieclaw_kernel import DURABLE_EVENTS
from movieclaw_sdk import Context, plugin
from movieclaw_sdk.events import LIBRARY_INGEST_COMPLETED, IngestCompleted

PLUGIN_ID = "hello-note"
SEEN_KEY = "seen"
LAST_TITLE_KEY = "last_title"
SEEN_LIMIT = 500


class Settings(BaseModel):
    """设置页能画出来的字段：布尔和字符串。"""

    enabled: bool = Field(
        default=True,
        title="启用",
        description="关闭后插件照常加载，但不再记笔记",
    )
    prefix: str = Field(
        default="",
        title="标题前缀",
        description="只记录标题以此开头的片子；留空则全部记录",
        max_length=40,
    )


def should_note(title: str, *, enabled: bool, prefix: str) -> bool:
    """要不要把这次入库记下来。前缀按标题开头匹配，空前缀表示全部。"""
    if not enabled:
        return False
    if not prefix:
        return True
    return title.startswith(prefix)


def remember(seen: list[str], event_id: str | None, *, limit: int = SEEN_LIMIT) -> list[str] | None:
    """可靠订阅至少送达一次。见过这个事件 id 就返回 None；否则返回要写回的列表。"""
    if event_id and event_id in seen:
        return None
    if not event_id:
        return list(seen)
    return [event_id, *seen][:limit]


@plugin(
    PLUGIN_ID,
    title="入库笔记",
    inject=(DURABLE_EVENTS, PLUGIN_DATA),
    permissions=(),
    config=Settings,
)
async def apply(ctx: Context) -> None:
    store = ctx.use(PLUGIN_DATA).scoped(ctx)
    raw = ctx.config
    settings = raw if isinstance(raw, Settings) else Settings.model_validate(raw or {})

    async def on_ingested(event: IngestCompleted) -> None:
        title = event.media.title
        if not should_note(title, enabled=settings.enabled, prefix=settings.prefix):
            return
        event_id = ctx.delivery.event_id if ctx.delivery else None
        seen = await store.get(SEEN_KEY, default=[])
        if not isinstance(seen, list):
            seen = []
        updated = remember([str(item) for item in seen], event_id)
        if updated is None:
            return
        if event_id:
            await store.set(SEEN_KEY, updated)
        await store.set(LAST_TITLE_KEY, title)
        ctx.logger.info("记下《%s》", title)

    ctx.on(LIBRARY_INGEST_COMPLETED, on_ingested, id="note", durable=True)
