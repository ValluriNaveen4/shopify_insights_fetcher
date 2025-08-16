from __future__ import annotations
import os, httpx, urllib.parse, tldextract
from ..config import get_settings

settings = get_settings()

BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

async def find_competitors(brand_url: str, limit: int = 5) -> list[str]:
    """Bonus: Use Bing Web Search API if key is provided, fallback to empty list."""
    if not settings.bing_api_key:
        return []
    domain = tldextract.extract(brand_url).registered_domain
    query = f"similar brands to {domain} site:shopify.com OR site:myshopify.com"
    headers = {"Ocp-Apim-Subscription-Key": settings.bing_api_key}
    params = {"q": query, "count": limit}
    async with httpx.AsyncClient(headers=headers, timeout=12) as client:
        r = await client.get(BING_ENDPOINT, params=params)
        r.raise_for_status()
        data = r.json()
    results = []
    for w in data.get("webPages", {}).get("value", []):
        url = w.get("url")
        if url:
            results.append(url)
    return results[:limit]
