"""LangChain ``@tool``-decorated functions available to the research agent."""
from app.tools.save_finding import save_findings
from app.tools.web_search import web_search

__all__ = ["save_findings", "web_search"]
