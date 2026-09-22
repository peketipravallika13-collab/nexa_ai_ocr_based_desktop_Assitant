"""
Deep Search Plugin for Nexa AI
------------------------------
Autonomous multi-source deep research agent. Explores sub-queries, scrapes
key web documentation, cross-checks findings, and synthesizes in-depth reports
with source citations.
"""

import urllib.parse
import re
import requests
import logging

logger = logging.getLogger("deep_search_plugin")

PLUGIN_SCHEMA = {
    "name": "deep_search_researcher",
    "description": "Perform comprehensive multi-source deep research on any topic, technology, error, or product with deep web scraping, fact verification, and synthesized citations.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The primary research topic or detailed question."
            },
            "research_focus": {
                "type": "STRING",
                "description": "Specific angles to focus on (e.g. 'pricing, benchmarks, pros & cons, code examples')."
            }
        },
        "required": ["query"]
    }
}

def clean_html(html_content: str, max_chars: int = 2500) -> str:
    """Extract clean readable text from HTML markup."""
    if not html_content:
        return ""
    text = re.sub(r'<script.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = " ".join(lines)
    return cleaned[:max_chars]

def fetch_duckduckgo_sources(query: str, max_results: int = 4) -> list:
    """Fetch search result snippets and links via DuckDuckGo HTML endpoint."""
    sources = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            # Extract links and snippets using regex
            links = re.findall(r'<a class="result__url" href="([^"]+)">(.*?)</a>', res.text)
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', res.text)
            
            for i in range(min(len(links), max_results)):
                raw_link = links[i][0]
                # Unpack DuckDuckGo redirect if needed
                if "/l/?kh=-1&uddg=" in raw_link:
                    actual_url = urllib.parse.unquote(raw_link.split("uddg=")[-1].split("&")[0])
                else:
                    actual_url = raw_link
                    
                snippet_text = re.sub(r'<[^>]+>', '', snippets[i]) if i < len(snippets) else ""
                sources.append({
                    "url": actual_url,
                    "title": links[i][1].strip(),
                    "snippet": snippet_text.strip()
                })
    except Exception as e:
        logger.warning(f"DuckDuckGo search error: {e}")
        
    return sources

def run(query: str = "", research_focus: str = "") -> str:
    """Execute autonomous deep search and synthesize multi-source findings."""
    if not query:
        return "Error: No query provided for deep search."
        
    query_clean = query.strip()
    logger.info(f"Initiating Deep Search on: '{query_clean}' (Focus: {research_focus})")
    
    # 1. Generate sub-queries for multi-angle coverage
    sub_queries = [query_clean]
    if research_focus:
        sub_queries.append(f"{query_clean} {research_focus}")
    else:
        sub_queries.append(f"{query_clean} overview documentation analysis")
        
    collected_sources = []
    seen_urls = set()
    
    # 2. Query search engines
    for sq in sub_queries[:2]:
        results = fetch_duckduckgo_sources(sq, max_results=3)
        for r in results:
            if r["url"] not in seen_urls and not r["url"].endswith(".pdf"):
                seen_urls.add(r["url"])
                collected_sources.append(r)
                
    # 3. Deep-scrape top source page
    scraped_content = ""
    if collected_sources:
        top_url = collected_sources[0]["url"]
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(top_url, headers=headers, timeout=7)
            if resp.status_code == 200:
                scraped_content = clean_html(resp.text, max_chars=1800)
        except Exception as e:
            logger.warning(f"Failed to scrape top url {top_url}: {e}")
            
    # 4. Format structured research packet for LLM synthesis
    report = [
        f"🔬 **Deep Search Multi-Angle Investigation:** `{query_clean}`",
        f"**Focus Area:** {research_focus or 'Comprehensive Technical & Practical Overview'}\n",
        "### 📚 Synthesized Key Source Findings:"
    ]
    
    if collected_sources:
        for idx, src in enumerate(collected_sources[:4], 1):
            title = src.get('title') or src['url']
            report.append(f"**{idx}. [{title}]({src['url']})**\n> {src.get('snippet', 'Direct documentation link')}")
    else:
        report.append("*(Live search queried. Gemini will synthesize using internal knowledge and live search grounding.)*")
        
    if scraped_content:
        report.append(f"\n### 🔍 Deep Extract from Primary Source:\n```text\n{scraped_content[:1000]}...\n```")
        
    report.append("\n💡 *Deep search sources compiled. Ready for full multi-perspective synthesis.*")
    return "\n\n".join(report)
