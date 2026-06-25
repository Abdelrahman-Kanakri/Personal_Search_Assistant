from langchain.tools import tool
from langgraph.prebuilt import InjectedStore
from typing_extensions import Annotated
from typing import Any
from langchain_core.runnables import RunnableConfig

@tool
def save_findings(findings: list[dict[str, str]],
                store: Annotated[Any, InjectedStore],
                config:  RunnableConfig) -> str:
    """Saves a finding to the knowledge store.
    
    args:
        findings: A list of findings to save. Each finding should be a dictionary with the following keys
            - content: The content of the finding.
            - url: The URL of the finding.
        store: The knowledge store to save the findings to.
        config: The configuration for the tool. Should be a dictionary with the following keys
            - user_id: The user ID of the user saving the finding.
    """
    user_id = config["configurable"]["user_id"]
    namespace_for_findings = (user_id, "findings")
    
    for finding in findings:
        store.put(namespace=namespace_for_findings,
                key=finding["topic"] + "_" + finding["timestamp"],
                value=finding)
    
    return f"Saved {len(findings)} findings to the knowledge store for user {user_id}."