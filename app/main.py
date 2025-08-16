from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from .schemas import ScrapeRequest, BrandContext, CompetitorResult
from .services.shopify_scraper import scrape_brand
from .services.competitors import find_competitors
from .db import init_db, SessionLocal, Brand, Product, Policy, FAQ
from .config import get_settings
from sqlalchemy.orm import Session

app = FastAPI(title="Shopify Store Insights-Fetcher", version="1.0.0")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/scrape", response_model=BrandContext, responses={401: {"description": "Website not found"}, 500: {"description": "Internal error"}})
async def scrape(req: ScrapeRequest, db: Session = Depends(get_db)):
    try:
        ctx = await scrape_brand(req.website_url)
    except Exception as e:
        msg = str(e).lower()
        if "not found" in msg or "404" in msg or "dns" in msg:
            raise HTTPException(status_code=401, detail="Website not found or inaccessible")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

    # Persist (Bonus) - idempotent upsert by base_url
    brand = db.query(Brand).filter(Brand.base_url == ctx.base_url).one_or_none()
    if not brand:
        brand = Brand(base_url=ctx.base_url)
        db.add(brand)
    brand.name = ctx.brand_name
    brand.about_text = ctx.about_text
    brand.emails = ",".join(ctx.contact_emails) if ctx.contact_emails else None
    brand.phones = ",".join(ctx.contact_phones) if ctx.contact_phones else None
    brand.socials = ctx.social_handles.model_dump()
    brand.important_links = ctx.important_links.model_dump()
    # Clear existing children
    db.query(Product).filter(Product.brand_id == brand.id).delete() if brand.id else None
    db.query(Policy).filter(Policy.brand_id == brand.id).delete() if brand.id else None
    db.query(FAQ).filter(FAQ.brand_id == brand.id).delete() if brand.id else None
    db.flush()
    # Add children
    for p in ctx.products:
        db.add(Product(
            brand=brand,
            title=p.title or "",
            handle=p.handle,
            product_type=p.product_type,
            vendor=p.vendor,
            status=p.status,
            tags=",".join(p.tags) if p.tags else None,
            image=p.image,
            url=p.url,
            raw=p.raw,
            is_hero=1 if p.is_hero else 0,
        ))
    for pol in ctx.policies:
        db.add(Policy(brand=brand, kind=pol.kind, url=pol.url, content=pol.content))
    for f in ctx.faqs:
        db.add(FAQ(brand=brand, question=f.question, answer=f.answer, url=f.url))
    db.commit()

    return JSONResponse(status_code=200, content=ctx.model_dump())

@app.get("/competitors", response_model=CompetitorResult)
async def competitors(website: str):
    comps = await find_competitors(website)
    return CompetitorResult(query=website, competitors=comps)

@app.get("/", include_in_schema=False)
def root_info():
    return {
        "message": "Shopify Store Insights-Fetcher is running.",
        "usage": {
            "POST /scrape": {"website_url": "https://examplebrand.com"},
            "GET /competitors": {"website": "https://examplebrand.com", "note": "Requires BING_SEARCH_API_KEY"},
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }
