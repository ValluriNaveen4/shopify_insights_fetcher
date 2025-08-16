# Shopify Store Insights-Fetcher (FastAPI)

A robust Python backend that scrapes public Shopify storefronts **without using the official Shopify API** and returns a structured JSON **Brand Context** with product catalog, hero products, policies, FAQs, socials, contacts, about text and important links. Includes optional persistence (SQLAlchemy with MySQL/SQLite) and a bonus competitor endpoint using Bing Web Search API.

---

## Features (Mandatory)
- **Whole Product Catalog** via `/products.json` pagination (limit 250/page).
- **Hero Products** parsed from homepage JSON-LD and product cards.
- **Policies**: privacy, returns/refund, shipping, terms (common Shopify slugs + fallback).
- **FAQs**: JSON-LD `FAQPage` and DOM heuristics.
- **Social Handles**: Instagram, Facebook, TikTok, YouTube, Twitter, Pinterest, LinkedIn.
- **Contacts**: Emails & phone numbers (regex over visible text).
- **About Text**: Longest paragraph from `/pages/about` (if available).
- **Important Links**: Contact, About, Blogs, Order Tracking, FAQ + Policy links.

## Bonus
- **/competitors** uses Bing Web Search API (optional, requires `BING_SEARCH_API_KEY`).
- **Persistence**: SQLAlchemy models with MySQL or SQLite (default).

---

## Quickstart

1. **Clone & install**

```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # adjust DB_URL and BING_SEARCH_API_KEY if needed
```

2. **Run**

```bash
uvicorn app.main:app --reload --port 8000
```

3. **Test in Swagger**  
Open: `http://127.0.0.1:8000/docs`

**POST /scrape** body:
```json
{ "website_url": "https://memy.co.in" }
```

**GET /competitors** (Bonus; needs API key):
```
/competitors?website=https://memy.co.in
```

---

## JSON Output (BrandContext)

```jsonc
{
  "brand_name": "ACME",
  "base_url": "https://acme.com",
  "products": [ { "title": "...", "handle": "...", "url": "..." } ],
  "hero_products": [ { "title": "...", "url": "..." } ],
  "policies": [ { "kind": "privacy", "url": "...", "content": "..." } ],
  "faqs": [ { "question": "Do you ship COD?", "answer": "Yes" } ],
  "social_handles": { "instagram": "...", "facebook": "..." },
  "contact_emails": ["support@acme.com"],
  "contact_phones": ["+1-555-..."],
  "about_text": "ACME is ...",
  "important_links": { "contact_us": "...", "faq": "...", "privacy": "..." }
}
```

---

## Notes & Design Choices

- **Resilience**: Retries (exponential backoff), graceful fallbacks.
- **Heuristics**: Multiple strategies for FAQs, hero products, links.
- **Extensibility**: Clear separation of concerns (services, schemas, db).
- **RESTful**: Clean Pydantic models and FastAPI validation.
- **Compliance**: Public pages only; robots.txt is not programmatically enforced—respect it for production use.

### Scaling Suggestions
- Async concurrency limits via `anyio` semaphore / task groups.
- Distributed scraping queue (Celery/RQ) for batch jobs.
- Caching layer (Redis) for popular stores.
- Proxy pool/headers rotation when needed.
- Add sitemap parsing to discover custom pages.

### MySQL Setup Example
Use `DB_URL=mysql+pymysql://user:pass@localhost:3306/brand_insights` and ensure the DB exists.

---

## Postman

Create a request:
- **POST** `http://127.0.0.1:8000/scrape`
- Body (JSON): `{ "website_url": "https://hairoriginals.com" }`

---

## Security & Legal

Scrape **only public** pages and comply with each site's Terms of Service and robots.txt. Do not overload servers. This project is for evaluation/demo purposes.
