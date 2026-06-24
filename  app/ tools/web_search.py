from langchain.tools import tool
from langchain_tavily import TavilySearch
from app.core import settings

import os 
os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the web for information about a topic.
    
    args: 
        query: The query to search for.
        max_results: The maximum number of results to return.
    """
    # Initialize the TavilySearch tool
    webSearch = TavilySearch(max_results=max_results)
    
    result = webSearch.invoke({"query": query})
    
    # List of documents that will be returned to the user. Each document is a dictionary with the following keys
    documents = []
    for item in result:
        documents.append({
            "content": item["content"],
            "url": item["url"],
        })
    
    return documents