"""Tavily-backed web search tool, exposed as a LangChain ``@tool``."""
import os

from langchain.tools import tool
from langchain_tavily import TavilySearch

from app.core import settings

os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web and return a list of result snippets with their source URLs.

    Args:
        query: The search query string.
        max_results: Maximum number of results to retrieve from Tavily.

    Returns:
        A list of dicts, each containing ``"content"`` (snippet text) and ``"url"``.
    """
    searcher = TavilySearch(max_results=max_results)
    results = searcher.invoke({"query": query})
    return [{"content": item["content"], "url": item["url"]} for item in results["results"]]
