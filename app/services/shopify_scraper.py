from __future__ import annotations
import httpx, json, re, asyncio, tldextract
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from typing import Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..schemas import BrandContext, ProductSchema, PolicySchema, FAQSchema, SocialHandles, ImportantLinks
from ..config import get_settings

settings = get_settings()

SHOPIFY_POLICY_SLUGS = {
    "privacy": ["/policies/privacy-policy", "/pages/privacy-policy", "/pages/privacy", "/privacy-policy"],
    "refund": ["/policies/refund-policy", "/pages/refund-policy", "/refund-policy"],
    "returns": ["/policies/return-policy", "/pages/return-policy", "/returns"],
    "shipping": ["/policies/shipping-policy", "/pages/shipping-policy", "/shipping-policy"],
    "terms": ["/policies/terms-of-service", "/pages/terms-of-service", "/terms-of-service"],
}

COMMON_LINK_SLUGS = {
    "contact_us": ["/pages/contact", "/contact", "/pages/contact-us", "/contact-us"],
    "about": ["/pages/about", "/pages/about-us", "/about", "/about-us"],
    "blogs": ["/blogs", "/blogs/news"],
    "order_tracking": ["/pages/track-order", "/pages/order-tracking", "/apps/track", "/a/track"],
    "faq": ["/pages/faq", "/pages/faqs", "/faq", "/faqs", "/pages/help", "/pages/support"],
}

SOCIAL_DOMAINS = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "tiktok": "tiktok.com",
    "youtube": "youtube.com",
    "twitter": "twitter.com",
    "pinterest": "pinterest.com",
    "linkedin": "linkedin.com",
}

def normalize_base(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return base

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=1, max=8), reraise=True)
async def fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    resp = await client.get(url, timeout=settings.request_timeout, headers={"User-Agent": settings.user_agent})
    resp.raise_for_status()
    return resp

async def try_json(client: httpx.AsyncClient, url: str) -> Optional[dict]:
    try:
        r = await fetch(client, url)
        if "application/json" in r.headers.get("Content-Type", "") or r.text.strip().startswith("{") or r.text.strip().startswith("["):
            return r.json()
    except Exception:
        return None
    return None

async def try_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
    try:
        r = await fetch(client, url)
        return r.text
    except Exception:
        return None

def extract_brand_name(soup: BeautifulSoup) -> Optional[str]:
    if soup.title and soup.title.string:
        return soup.title.string.strip().split("|")[0].strip()
    og = soup.find("meta", property="og:site_name")
    if og and og.get("content"):
        return og["content"].strip()
    header_logo_alt = soup.select_one("header img[alt]")
    if header_logo_alt:
        return header_logo_alt["alt"].strip()[:128]
    return None

def extract_jsonld_products(html: str) -> list[ProductSchema]:
    results: list[ProductSchema] = []
    for tag in BeautifulSoup(html, "lxml").find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        items = []
        if isinstance(data, dict) and data.get("@type") in ("Product", "ItemList"):
            if data.get("@type") == "Product":
                items = [data]
            elif data.get("@type") == "ItemList":
                items = [it.get("item") or it for it in data.get("itemListElement", [])]
        elif isinstance(data, list):
            for d in data:
                if isinstance(d, dict) and d.get("@type") == "Product":
                    items.append(d)
        for d in items:
            try:
                results.append(ProductSchema(
                    title=d.get("name"),
                    url=d.get("url"),
                    image=(d.get("image")[0] if isinstance(d.get("image"), list) else d.get("image")),
                    raw=d
                ))
            except Exception:
                pass
    return results

def extract_socials(soup: BeautifulSoup, base: str) -> SocialHandles:
    links = {name: None for name in SOCIAL_DOMAINS.keys()}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        for name, dom in SOCIAL_DOMAINS.items():
            if dom in href:
                links[name] = href
    return SocialHandles(**links)

def extract_contacts(soup: BeautifulSoup) -> tuple[list[str], list[str]]:
    emails = set()
    phones = set()
    text = soup.get_text(" ", strip=True)
    for email in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
        emails.add(email.lower())
    for phone in re.findall(r"(?:\+\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{4}", text):
        phones.add(phone.strip())
    return list(emails), list(phones)

def extract_faqs_from_jsonld(html: str) -> list[FAQSchema]:
    faqs: list[FAQSchema] = []
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except Exception:
            continue
        blocks = data if isinstance(data, list) else [data]
        for d in blocks:
            if isinstance(d, dict) and d.get("@type") == "FAQPage":
                for item in d.get("mainEntity", []):
                    q = item.get("name") or item.get("question")
                    a = None
                    accepted = item.get("acceptedAnswer") or {}
                    if isinstance(accepted, dict):
                        a = accepted.get("text")
                    faqs.append(FAQSchema(question=(q or "").strip(), answer=(a or "").strip()))
    return faqs

def extract_faqs_from_dom(html: str) -> list[FAQSchema]:
    faqs: list[FAQSchema] = []
    soup = BeautifulSoup(html, "lxml")
    # Heuristics: pairs of headings and following paragraphs/divs
    for qnode in soup.select("details summary, .faq-item h3, .faq h3, .accordion__title, h3, h4"):
        qtext = qnode.get_text(" ", strip=True)
        if len(qtext) < 5 or len(qtext) > 200:
            continue
        # find sibling or next element as answer
        ans_node = qnode.find_next_sibling(["div","p","section"])
        if not ans_node:
            continue
        atext = ans_node.get_text(" ", strip=True)
        if len(atext) < 5:
            continue
        # simple filter: presence of question-like punctuation or words
        if re.search(r"\?$|\b(how|what|when|where|do|does|is|can|why)\b", qtext, re.I):
            faqs.append(FAQSchema(question=qtext, answer=atext[:2000]))
    # de-duplicate by question
    uniq = {}
    for f in faqs:
        uniq.setdefault(f.question.lower(), f)
    return list(uniq.values())

def join_if_abs(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(base, href)

async def get_products(client: httpx.AsyncClient, base: str) -> list[ProductSchema]:
    prods: list[ProductSchema] = []
    for page in range(1, settings.max_products_pages + 1):
        url = f"{base}/products.json?limit=250&page={page}"
        data = await try_json(client, url)
        if not data or not data.get("products"):
            break
        for p in data["products"]:
            image = (p.get("image") or {}).get("src") if isinstance(p.get("image"), dict) else None
            prods.append(ProductSchema(
                title=p.get("title"),
                handle=p.get("handle"),
                product_type=p.get("product_type"),
                vendor=p.get("vendor"),
                status=p.get("status") or p.get("published_scope"),
                tags=p.get("tags", "").split(",") if isinstance(p.get("tags"), str) and p.get("tags") else None,
                image=image,
                url=f"{base}/products/{p.get('handle')}" if p.get("handle") else None,
                raw=p
            ))
    return prods

async def get_homepage_and_hero(client: httpx.AsyncClient, base: str) -> tuple[str | None, list[ProductSchema], BrandContext]:
    html = await try_html(client, base)
    hero: list[ProductSchema] = []
    brand_name: Optional[str] = None
    about_text: Optional[str] = None
    socials = SocialHandles()
    emails: list[str] = []
    phones: list[str] = []
    important_links = ImportantLinks()

    if html:
        soup = BeautifulSoup(html, "lxml")
        brand_name = extract_brand_name(soup)
        hero = extract_jsonld_products(html)
        # also scrape product cards
        for card in soup.select("a[href*='/products/']"):
            title = card.get("title") or card.get_text(" ", strip=True)
            href = join_if_abs(base, card.get("href"))
            if title and href:
                hero.append(ProductSchema(title=title.strip()[:256], url=href, is_hero=True))
        # contacts + socials
        s = extract_socials(soup, base)
        socials = s
        e, p = extract_contacts(soup)
        emails, phones = e, p
        # important links
        for key, candidates in {**SHOPIFY_POLICY_SLUGS, **COMMON_LINK_SLUGS}.items():
            for c in candidates:
                link = soup.find("a", href=re.compile(re.escape(c)))
                if link:
                    url = join_if_abs(base, link.get("href"))
                    if key in SHOPIFY_POLICY_SLUGS:
                        setattr(important_links, key if key in ["privacy","refund","returns","shipping","terms"] else key, url)
                    else:
                        setattr(important_links, key, url)
                    break
        # About text heuristic
        about_link = important_links.about or "/pages/about"
        about_html = await try_html(client, join_if_abs(base, about_link)) if about_link else None
        if about_html:
            about_soup = BeautifulSoup(about_html, "lxml")
            # pick longest paragraph
            paras = sorted([p.get_text(" ", strip=True) for p in about_soup.find_all("p")], key=len, reverse=True)
            if paras:
                about_text = paras[0][:4000]

    # de-duplicate hero
    seen = set()
    uniq_hero = []
    for h in hero:
        key = (h.title or "") + (h.url or "")
        if key and key not in seen:
            seen.add(key)
            h.is_hero = True
            uniq_hero.append(h)
    ctx = BrandContext(
        brand_name=brand_name,
        base_url=base,
        hero_products=uniq_hero,
        social_handles=socials,
        contact_emails=emails,
        contact_phones=phones,
        about_text=about_text,
        important_links=important_links,
    )
    return html, uniq_hero, ctx

async def get_policies(client: httpx.AsyncClient, base: str, homepage_html: Optional[str]) -> list[PolicySchema]:
    results: list[PolicySchema] = []
    # First, try known slugs
    for kind, paths in SHOPIFY_POLICY_SLUGS.items():
        content = None
        url = None
        for p in paths:
            url_try = f"{base}{p}"
            html = await try_html(client, url_try)
            if html and ("privacy" in kind or "policy" in html.lower() or "return" in html.lower() or "refund" in html.lower()):
                soup = BeautifulSoup(html, "lxml")
                body = soup.select_one("main") or soup.select_one("article") or soup
                text = body.get_text(" ", strip=True)
                if len(text) > 80:
                    content = text[:8000]
                    url = url_try
                    break
        if url or content:
            results.append(PolicySchema(kind=kind, url=url, content=content))
    # Fallback: parse homepage for links containing 'policy', 'privacy', etc.
    if homepage_html:
        soup = BeautifulSoup(homepage_html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            txt = a.get_text(" ", strip=True).lower()
            if any(k in href.lower() or k in txt for k in ["privacy", "refund", "return", "shipping", "terms"]):
                absolute = join_if_abs(base, href)
                html = await try_html(client, absolute)
                if not html:
                    continue
                body = BeautifulSoup(html, "lxml").select_one("main") or BeautifulSoup(html, "lxml")
                text = body.get_text(" ", strip=True)
                if len(text) > 80:
                    kind = "privacy" if "privacy" in href.lower() else "refund" if "refund" in href.lower() else "returns" if "return" in href.lower() else "shipping" if "shipping" in href.lower() else "terms"
                    # Avoid duplicates of same kind
                    if not any(p.kind == kind for p in results):
                        results.append(PolicySchema(kind=kind, url=absolute, content=text[:8000]))
    return results

async def get_faqs(client: httpx.AsyncClient, base: str, homepage_html: Optional[str], important_links: ImportantLinks) -> list[FAQSchema]:
    faqs: list[FAQSchema] = []
    # Try explicit FAQ links
    for path in COMMON_LINK_SLUGS["faq"]:
        html = await try_html(client, f"{base}{path}")
        if html:
            faqs.extend(extract_faqs_from_jsonld(html) or extract_faqs_from_dom(html))
    # If important_links.faq is set from homepage, use it
    if important_links and important_links.faq:
        html = await try_html(client, important_links.faq if important_links.faq.startswith("http") else f"{base}{important_links.faq}")
        if html:
            faqs.extend(extract_faqs_from_jsonld(html) or extract_faqs_from_dom(html))
    # Fallback: scan homepage
    if homepage_html and not faqs:
        faqs.extend(extract_faqs_from_jsonld(homepage_html) or extract_faqs_from_dom(homepage_html))
    # Dedup
    uniq = {}
    for f in faqs:
        key = f.question.strip().lower()
        if key and key not in uniq:
            uniq[key] = f
    return list(uniq.values())

async def scrape_brand(website_url: str) -> BrandContext:
    base = normalize_base(website_url)
    async with httpx.AsyncClient(follow_redirects=True, headers={"User-Agent": settings.user_agent}) as client:
        homepage_html, hero, ctx = await get_homepage_and_hero(client, base)
        products = await get_products(client, base)
        # mark heroes by URL match
        hero_urls = {h.url for h in hero if h.url}
        for p in products:
            if p.url in hero_urls:
                p.is_hero = True
        policies = await get_policies(client, base, homepage_html)
        faqs = await get_faqs(client, base, homepage_html, ctx.important_links)
        # Attach products & policies & faqs
        ctx.products = products
        ctx.policies = policies
        ctx.faqs = faqs
        return ctx
