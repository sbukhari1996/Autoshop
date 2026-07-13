"""
AutoEst Pro - Playwright Scraper Worker
─────────────────────────────────────────────────────────────────
Polls the scrape_jobs table for pending jobs and executes them.

Job types:
  'part'        → scrape MSRP for a specific part number
  'vin_diagram' → download SVG explosion diagrams for a VIN

Anti-bot strategy:
  - Random delays between requests (SCRAPE_DELAY_MIN to SCRAPE_DELAY_MAX seconds)
  - Realistic browser headers (Chrome/Win11 UA)
  - Randomized viewport sizes
  - Stealth: disable webdriver flag, add navigator.plugins
  - Retry with exponential backoff on failure

Target sites (RevolutionParts / SimplePart white-label network):
  Primary:   https://www.hondaautomotiveparts.com
  Fallback:  https://www.hondapartnow.com
  Universal: search by part number across dealer network
"""

import asyncio
import json
import logging
import os
import random
import time
import re
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ─── Config ─────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("scraper")

DATABASE_URL   = os.getenv("DATABASE_URL", "postgresql://autoest:autoest_secret@db:5432/autoest")
SVG_DIR        = os.getenv("SVG_DIR", "/app/svgs")
DELAY_MIN      = float(os.getenv("SCRAPE_DELAY_MIN", "2"))
DELAY_MAX      = float(os.getenv("SCRAPE_DELAY_MAX", "5"))
POLL_INTERVAL  = int(os.getenv("POLL_INTERVAL_SECS", "10"))
MAX_RETRIES    = 3

os.makedirs(SVG_DIR, exist_ok=True)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

# ─── Realistic browser profile ───────────────────────────────────
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

EXTRA_HEADERS = {
    "Accept":           "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language":  "en-US,en;q=0.9",
    "Accept-Encoding":  "gzip, deflate, br",
    "Connection":       "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":   "document",
    "Sec-Fetch-Mode":   "navigate",
    "Sec-Fetch-Site":   "none",
    "Sec-Fetch-User":   "?1",
}

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
    {"width": 1280, "height": 800},
]

# ─── Part number target sites ────────────────────────────────────
DEALER_SITES = [
    {
        "name":     "Honda Parts Now",
        "url":      "https://www.hondapartnow.com/search.html?query={part_number}",
        "make":     "honda",
        "selectors": {
            "price":        [".price", "[itemprop='price']", ".part-price", ".msrp"],
            "description":  [".product-name h1", ".item-title", "[itemprop='name']"],
            "part_number":  [".part-number", "[itemprop='sku']", ".sku"],
            "svg_link":     ["a[href*='.svg']", "img[src*='.svg']"],
        }
    },
    {
        "name":     "Majestic Honda",
        "url":      "https://www.majesticHonda.com/parts/search/?q={part_number}",
        "make":     "honda",
        "selectors": {
            "price":        ["[data-price]", ".price-value", ".part-price .amount"],
            "description":  [".part-name", ".product-title h1"],
            "part_number":  [".partnumber", ".part-num"],
            "svg_link":     [],
        }
    },
    {
        "name":     "RevolutionParts Generic",
        "url":      "https://api.revolutionparts.com/v1/search?term={part_number}&format=json",
        "make":     "any",
        "is_api":   True,
    }
]


# ─── Stealth helper ──────────────────────────────────────────────

async def stealth_page(browser: Browser) -> Page:
    viewport = random.choice(VIEWPORTS)
    ctx = await browser.new_context(
        user_agent=UA,
        viewport=viewport,
        locale="en-US",
        timezone_id="America/New_York",
        extra_http_headers=EXTRA_HEADERS,
    )
    page = await ctx.new_page()
    # Remove webdriver fingerprint
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {} };
    """)
    return page


async def random_delay():
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# ─── Price extraction ────────────────────────────────────────────

async def extract_price(page: Page, selectors: list) -> Optional[float]:
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                raw = await el.inner_text()
                # Strip currency symbols, commas
                clean = re.sub(r"[^\d.]", "", raw.strip())
                if clean:
                    return float(clean)
                # Try data-price attribute
                attr = await el.get_attribute("data-price") or await el.get_attribute("content")
                if attr:
                    clean = re.sub(r"[^\d.]", "", attr)
                    if clean:
                        return float(clean)
        except Exception:
            continue
    return None


async def extract_text(page: Page, selectors: list) -> Optional[str]:
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                txt = await el.inner_text()
                if txt.strip():
                    return txt.strip()
        except Exception:
            continue
    return None


# ─── SVG Download ────────────────────────────────────────────────

async def download_svg(page: Page, url: str, filename: str) -> Optional[str]:
    try:
        resp = await page.request.get(url, headers=EXTRA_HEADERS)
        if resp.ok:
            content = await resp.body()
            if b"<svg" in content or b"<?xml" in content:
                path = os.path.join(SVG_DIR, filename)
                with open(path, "wb") as f:
                    f.write(content)
                log.info(f"SVG saved: {path}")
                return path
    except Exception as e:
        log.warning(f"SVG download failed {url}: {e}")
    return None


async def find_and_download_svgs(page: Page, part_number: str) -> Optional[str]:
    """Find SVG diagram links on current page and download the first valid one."""
    svg_path = None
    try:
        # Look for SVG links
        links = await page.query_selector_all("a[href*='.svg'], img[src*='.svg'], a[href*='diagram']")
        for link in links[:3]:
            href = await link.get_attribute("href") or await link.get_attribute("src")
            if href:
                if not href.startswith("http"):
                    href = f"{page.url.split('/')[0]}//{page.url.split('/')[2]}{href}"
                fname = f"{part_number.replace('/', '_')}_diagram.svg"
                result = await download_svg(page, href, fname)
                if result:
                    svg_path = result
                    break
    except Exception as e:
        log.warning(f"SVG search error: {e}")
    return svg_path


# ─── Scrape a single part ────────────────────────────────────────

async def scrape_part(browser: Browser, part_number: str,
                       make: Optional[str] = None,
                       model: Optional[str] = None,
                       year: Optional[int] = None) -> Optional[dict]:

    for site in DEALER_SITES:
        if site.get("make") not in ("any", None) and make:
            if site["make"].lower() not in make.lower():
                continue

        if site.get("is_api"):
            continue  # API fallback handled separately

        url = site["url"].format(part_number=part_number)
        log.info(f"Scraping {site['name']} for {part_number}: {url}")

        for attempt in range(MAX_RETRIES):
            page = await stealth_page(browser)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await random_delay()

                selectors = site["selectors"]
                price       = await extract_price(page, selectors["price"])
                description = await extract_text(page, selectors["description"])
                svg_path    = await find_and_download_svgs(page, part_number)

                await page.context.close()

                if price:
                    return {
                        "part_number":      part_number.upper(),
                        "description":      description or part_number,
                        "msrp":             price,
                        "source_url":       url,
                        "dealer_name":      site["name"],
                        "make":             make,
                        "model":            model,
                        "year":             year,
                        "svg_local_path":   svg_path,
                    }
            except Exception as e:
                log.warning(f"Attempt {attempt+1} failed for {site['name']}: {e}")
                await page.context.close()
                await asyncio.sleep(2 ** attempt)

    log.warning(f"No price found for {part_number} across all sites")
    return None


# ─── VIN Diagram Scrape ──────────────────────────────────────────

async def scrape_vin_diagrams(browser: Browser, vin: str) -> list:
    """
    Navigate to Honda parts site, search by VIN, and download
    all available SVG explosion diagrams.
    """
    saved = []
    url = f"https://www.hondapartnow.com/vin/{vin}"
    page = await stealth_page(browser)
    try:
        log.info(f"Fetching VIN diagrams for {vin}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await random_delay()

        # Find all diagram section links
        section_links = await page.query_selector_all("a[href*='diagram'], a[href*='section']")
        log.info(f"Found {len(section_links)} diagram links for VIN {vin}")

        for i, link in enumerate(section_links[:30]):  # cap at 30 sections
            href = await link.get_attribute("href")
            section_name = (await link.inner_text()).strip().replace(" ", "_").replace("/", "-")[:40]
            if not href:
                continue
            if not href.startswith("http"):
                base = f"{page.url.split('/')[0]}//{page.url.split('/')[2]}"
                href = f"{base}{href}"

            sub_page = await stealth_page(browser)
            try:
                await sub_page.goto(href, wait_until="domcontentloaded", timeout=20000)
                await random_delay()
                fname = f"{vin}_{i:02d}_{section_name}.svg"
                result = await find_and_download_svgs(sub_page, f"{vin}_{section_name}")
                if result:
                    saved.append({"section": section_name, "path": result})
            except Exception as e:
                log.warning(f"Section diagram failed {href}: {e}")
            finally:
                await sub_page.context.close()

    except Exception as e:
        log.error(f"VIN diagram scrape failed for {vin}: {e}")
    finally:
        await page.context.close()

    return saved


# ─── DB helpers ──────────────────────────────────────────────────

def save_part_to_db(data: dict):
    with Session() as db:
        db.execute(text("""
            INSERT INTO scraped_parts
                (part_number, description, msrp, source_url, dealer_name,
                 make, model, year, svg_local_path, scraped_at)
            VALUES
                (:part_number, :description, :msrp, :source_url, :dealer_name,
                 :make, :model, :year, :svg_local_path, NOW())
            ON CONFLICT (part_number, dealer_name)
            DO UPDATE SET
                msrp=EXCLUDED.msrp,
                description=EXCLUDED.description,
                svg_local_path=EXCLUDED.svg_local_path,
                scraped_at=NOW()
        """), data)
        db.commit()


def mark_job(job_id: int, status: str, error: Optional[str] = None):
    with Session() as db:
        db.execute(text("""
            UPDATE scrape_jobs
            SET status=:status, error_message=:error, completed_at=NOW()
            WHERE id=:id
        """), {"status": status, "error": error, "id": job_id})
        db.commit()


def get_pending_jobs() -> list:
    with Session() as db:
        rows = db.execute(text("""
            SELECT id, job_type, payload FROM scrape_jobs
            WHERE status = 'pending'
            ORDER BY created_at
            LIMIT 5
        """)).mappings().all()
        return [dict(r) for r in rows]


# ─── Main worker loop ────────────────────────────────────────────

async def run_worker():
    log.info("AutoEst Pro Scraper Worker starting...")
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ]
        )
        log.info("Chromium launched. Polling for jobs...")

        while True:
            jobs = get_pending_jobs()
            if not jobs:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            for job in jobs:
                job_id   = job["id"]
                job_type = job["job_type"]
                payload  = json.loads(job["payload"])

                log.info(f"Processing job #{job_id}: {job_type} → {payload}")

                # Mark running
                mark_job(job_id, "running")

                try:
                    if job_type == "part":
                        result = await scrape_part(
                            browser,
                            part_number=payload["part_number"],
                            make=payload.get("make"),
                            model=payload.get("model"),
                            year=payload.get("year"),
                        )
                        if result:
                            save_part_to_db(result)
                            mark_job(job_id, "done")
                            log.info(f"Job #{job_id} done: ${result['msrp']} for {result['part_number']}")
                        else:
                            mark_job(job_id, "failed", "No price found on any dealer site")

                    elif job_type == "vin_diagram":
                        diagrams = await scrape_vin_diagrams(browser, payload["vin"])
                        mark_job(job_id, "done" if diagrams else "failed",
                                 None if diagrams else "No SVG diagrams found")
                        log.info(f"Job #{job_id}: {len(diagrams)} diagrams saved for VIN {payload['vin']}")

                    else:
                        mark_job(job_id, "failed", f"Unknown job type: {job_type}")

                except Exception as e:
                    log.error(f"Job #{job_id} crashed: {e}")
                    mark_job(job_id, "failed", str(e))

                await random_delay()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run_worker())
