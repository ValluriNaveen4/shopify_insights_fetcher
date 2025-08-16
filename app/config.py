from pydantic import BaseModel, Field
from functools import lru_cache
import os

class Settings(BaseModel):
    db_url: str = Field(default=os.getenv("DB_URL", "sqlite:///./brand_insights.db"))
    bing_api_key: str | None = Field(default=os.getenv("BING_SEARCH_API_KEY"))
    user_agent: str = Field(default=os.getenv("USER_AGENT", "Shopify-Insights-Fetcher/1.0 (+https://example.com)"))
    request_timeout: float = 15.0
    max_products_pages: int = 20  # 20 * 250 = 5k products
    max_concurrent_requests: int = 5

@lru_cache
def get_settings() -> Settings:
    return Settings()
