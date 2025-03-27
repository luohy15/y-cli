import datetime

# Get current datetime
current_time = datetime.datetime.now()
formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
time_prompt = f"Current Time: {formatted_time}"

deep_research_prompt = """
====

DEEP RESEARCH

For deep research tasks that require fetching content from multiple web pages, you can use the following two-phase approach:

1. First, search for information using the search server(such as brave-searc, tavily, exa) to get a list of relevant URLs:
<use_mcp_tool>
<server_name>brave-search</server_name>
<tool_name>brave_web_search</tool_name>
<arguments>
{
  "query": "your search query here"
}
</arguments>
</use_mcp_tool>

2. Then, analyze the search results and select the most relevant URLs for detailed fetching, use server such as fetcher-mcp:
<use_mcp_tool>
<server_name>fetcher-mcp</server_name>
<tool_name>fetch_urls</tool_name>
<arguments>
{
  "search_results": "the search results from step 1",
  "rationale": "explain why you're selecting these specific URLs",
  "urls": ["url1", "url2", "url3", "url4", "url5"]
}
</arguments>
</use_mcp_tool>

The system will fetch these URLs concurrently and return their combined content, which you can then analyze to provide a comprehensive summary."
"""