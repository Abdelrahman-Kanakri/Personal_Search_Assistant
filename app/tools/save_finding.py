"""Tool for persisting research findings to the LangGraph cross-session store."""

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import InjectedStore
from typing_extensions import Annotated


# No @tool decorator is required here because this is a node, not a tool.
async def save_findings(
    findings: list[dict[str, str]],
    store: Annotated[Any, InjectedStore],
    config: RunnableConfig,
) -> str:
    """Write a batch of research findings to the user's persistent store namespace.

    The store key is ``(user_id, 'findings')``, so each user's findings are
    isolated from one another.  Within that namespace each finding is keyed by
    ``topic + timestamp`` to avoid collisions across research sessions.

    Args:
        findings: List of finding dicts, each containing ``"topic"``,
            ``"content"``, and ``"timestamp"`` keys.
        store: LangGraph store injected at runtime via ``InjectedStore``.
        config: Runnable config; must carry ``configurable.user_id``.

    Returns:
        A confirmation string reporting how many findings were saved.
    """
    user_id = config["configurable"]["user_id"]
    namespace = (user_id, "findings")

    for finding in findings:
        await store.aput(
            namespace=namespace,
            key=f"{finding['topic']}_{finding['timestamp']}",
            value=finding,
        )

    return f"Saved {len(findings)} findings to the knowledge store for user {user_id}."
