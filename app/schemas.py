from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Dict, Any

class ProductSchema(BaseModel):
    title: str
    handle: Optional[str] = None
    product_type: Optional[str] = None
    vendor: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[list[str]] = None
    image: Optional[HttpUrl | str] = None
    url: Optional[HttpUrl | str] = None
    raw: Optional[Dict[str, Any]] = None
    is_hero: bool = False

class PolicySchema(BaseModel):
    kind: str
    url: Optional[str] = None
    content: Optional[str] = None

class FAQSchema(BaseModel):
    question: str
    answer: Optional[str] = None
    url: Optional[str] = None

class SocialHandles(BaseModel):
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    youtube: Optional[str] = None
    twitter: Optional[str] = None
    pinterest: Optional[str] = None
    linkedin: Optional[str] = None

class ImportantLinks(BaseModel):
    contact_us: Optional[str] = None
    about: Optional[str] = None
    blogs: Optional[str] = None
    order_tracking: Optional[str] = None
    terms: Optional[str] = None
    shipping: Optional[str] = None
    privacy: Optional[str] = None
    refund: Optional[str] = None
    returns: Optional[str] = None
    faq: Optional[str] = None

class BrandContext(BaseModel):
    brand_name: Optional[str] = None
    base_url: str
    products: List[ProductSchema] = Field(default_factory=list)
    hero_products: List[ProductSchema] = Field(default_factory=list)
    policies: List[PolicySchema] = Field(default_factory=list)
    faqs: List[FAQSchema] = Field(default_factory=list)
    social_handles: SocialHandles = Field(default_factory=SocialHandles)
    contact_emails: List[str] = Field(default_factory=list)
    contact_phones: List[str] = Field(default_factory=list)
    about_text: Optional[str] = None
    important_links: ImportantLinks = Field(default_factory=ImportantLinks)

class ScrapeRequest(BaseModel):
    website_url: str

class CompetitorResult(BaseModel):
    query: str
    competitors: list[str]
