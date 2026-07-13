"""
ProEstimator Web-Est Scraper
─────────────────────────────────────────────────────────────────
Scrapes ALL available data from proestimator.web-est.com for a given
shop ID (default: 53288). Supports two auth modes:

  1. Cookie-based (preferred, no login required):
     Export cookies from your browser after logging in and set
     PROEST_COOKIES_JSON env var (JSON string from "Edit This Cookie"
     Chrome extension or similar).

  2. Email + Password login:
     Set PROEST_EMAIL and PROEST_PASSWORD env vars.

What it scrapes:
  - All estimates (list + full detail page for each)
  - Customer info per estimate
  - Vehicle info (VIN, year, make, model, color, etc.)
  - Line items: parts, labor, paint, sublet, other charges
  - Totals: parts, labor, tax, deductible, net due
  - Insurance / claim details
  - Supplement history
  - Photos/attachments (downloads them locally)
  - Rate profiles / labor rates

Output:
  - JSON dump:  scraped_data/proestimator_full_<timestamp>.json
  - CSV dump:   scraped_data/estimates_summary.csv
  - Photos:     scraped_data/photos/<estimate_id>/

Usage:
  # Cookie mode (recommended):
  export PROEST_COOKIES_JSON='[{"name":"session","value":"abc123",...}]'
  python proestimator_scraper.py --shop-id 53288

  # Email/password mode:
  export PROEST_EMAIL="you@example.com"
  export PROEST_PASSWORD="yourpassword"
  python proestimator_scraper.py --shop-id 53288

  # Limit for testing:
  python proestimator_scraper.py --shop-id 53288 --max-estimates 10
"""

import asyncio
import csv
import json
import logging
import os
import re
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from playwright.async_api import async_playwright, Page, BrowserContext

# ─── Config ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("proest_scraper")

BASE_URL     = "https://proestimator.web-est.com"
OUTPUT_DIR   = Path("scraped_data")
PHOTOS_DIR   = OUTPUT_DIR / "photos"
DELAY_MIN    = 1.5   # seconds between requests (be polite)
DELAY_MAX    = 3.0

OUTPUT_DIR.mkdir(exist_ok=True)
PHOTOS_DIR.mkdir(exist_ok=True)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ─── Helpers ─────────────────────────────────────────────────────

def clean(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def to_float(text: str) -> Optional[float]:
    try:
        return float(re.sub(r"[^\d.\-]", "", text or ""))
    except (ValueError, TypeError):
        return None


async def delay():
    import random
    await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


async def safe_text(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        return clean(await el.inner_text()) if el else ""
    except Exception:
        return ""


async def safe_attr(page: Page, selector: str, attr: str) -> str:
    try:
        el = await page.query_selector(selector)
        return clean(await el.get_attribute(attr)) if el else ""
    except Exception:
        return ""


async def safe_val(page: Page, selector: str) -> str:
    try:
        el = await page.query_selector(selector)
        return clean(await el.input_value()) if el else ""
    except Exception:
        return ""


async def table_to_dicts(page: Page, table_selector: str) -> list[dict]:
    """Extract an HTML table into a list of dicts keyed by header."""
    try:
        table = await page.query_selector(table_selector)
        if not table:
            return []
        headers = []
        header_cells = await table.query_selector_all("thead th, thead td, tr:first-child th, tr:first-child td")
        for h in header_cells:
            headers.append(clean(await h.inner_text()))
        rows = []
        data_rows = await table.query_selector_all("tbody tr")
        if not data_rows:
            # fallback: all rows except first
            all_rows = await table.query_selector_all("tr")
            data_rows = all_rows[1:]
        for row in data_rows:
            cells = await row.query_selector_all("td")
            vals = [clean(await c.inner_text()) for c in cells]
            if not any(vals):
                continue
            row_dict = {}
            for i, h in enumerate(headers):
                row_dict[h] = vals[i] if i < len(vals) else ""
            # also include unnamed cols
            for i in range(len(headers), len(vals)):
                row_dict[f"col_{i}"] = vals[i]
            rows.append(row_dict)
        return rows
    except Exception as e:
        log.debug(f"table_to_dicts failed for {table_selector}: {e}")
        return []


# ─── Auth ────────────────────────────────────────────────────────

async def authenticate(context: BrowserContext) -> bool:
    """
    Attempt cookie-based auth first, then email/password.
    Returns True if authenticated.
    """
    cookies_json = os.getenv("PROEST_COOKIES_JSON", "")
    email        = os.getenv("PROEST_EMAIL", "")
    password     = os.getenv("PROEST_PASSWORD", "")

    page = await context.new_page()

    # ── Method 1: inject cookies ──────────────────────────────
    if cookies_json:
        log.info("Auth mode: injecting browser cookies")
        try:
            raw_cookies = json.loads(cookies_json)
            playwright_cookies = []
            for c in raw_cookies:
                pc = {
                    "name":   c.get("name", c.get("Name", "")),
                    "value":  c.get("value", c.get("Value", "")),
                    "domain": c.get("domain", c.get("Domain", ".web-est.com")),
                    "path":   c.get("path", c.get("Path", "/")),
                }
                if "secure" in c:
                    pc["secure"] = bool(c["secure"])
                if "httpOnly" in c:
                    pc["httpOnly"] = bool(c["httpOnly"])
                if "sameSite" in c and c["sameSite"] in ("Strict", "Lax", "None"):
                    pc["sameSite"] = c["sameSite"]
                playwright_cookies.append(pc)
            await context.add_cookies(playwright_cookies)
            log.info(f"Injected {len(playwright_cookies)} cookies")

            # Verify we're logged in
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            await delay()
            title = await page.title()
            log.info(f"Page title after cookie inject: {title}")
            if "login" not in title.lower() and "sign in" not in title.lower():
                await page.close()
                return True
            log.warning("Cookie auth failed (redirected to login), trying email/password...")
        except Exception as e:
            log.error(f"Cookie injection error: {e}")

    # ── Method 2: email + password ────────────────────────────
    if email and password:
        log.info(f"Auth mode: email/password login as {email}")
        try:
            await page.goto(f"{BASE_URL}/login", wait_until="networkidle")
            await delay()

            # Try common login field selectors
            for email_sel in ["#email", "input[name='email']", "input[type='email']", "#username", "input[name='username']"]:
                el = await page.query_selector(email_sel)
                if el:
                    await el.fill(email)
                    break

            for pass_sel in ["#password", "input[name='password']", "input[type='password']"]:
                el = await page.query_selector(pass_sel)
                if el:
                    await el.fill(password)
                    break

            # Submit
            for submit_sel in ["button[type='submit']", "input[type='submit']", "#login-btn", ".login-btn", "button:has-text('Login')", "button:has-text('Sign In')"]:
                el = await page.query_selector(submit_sel)
                if el:
                    await el.click()
                    break

            await page.wait_for_load_state("networkidle")
            await delay()

            title = await page.title()
            url   = page.url
            log.info(f"Post-login URL: {url} | title: {title}")

            if "login" not in url.lower() and "login" not in title.lower():
                # Save cookies for reference
                cookies = await context.cookies()
                cookie_path = OUTPUT_DIR / "session_cookies.json"
                cookie_path.write_text(json.dumps(cookies, indent=2))
                log.info(f"Logged in successfully. Cookies saved to {cookie_path}")
                await page.close()
                return True
            else:
                log.error("Login failed — still on login page")
        except Exception as e:
            log.error(f"Login error: {e}")

    await page.close()
    log.error("Authentication failed. Set PROEST_COOKIES_JSON or PROEST_EMAIL + PROEST_PASSWORD")
    return False


# ─── Estimate List ────────────────────────────────────────────────

async def get_estimate_list(page: Page, shop_id: int) -> list[dict]:
    """Get list of all estimates for the shop."""
    estimates = []

    # Common URL patterns for ProEstimator
    list_urls = [
        f"{BASE_URL}/{shop_id}",
        f"{BASE_URL}/{shop_id}/estimates",
        f"{BASE_URL}/estimating/{shop_id}",
        f"{BASE_URL}/estimates?shop={shop_id}",
        f"{BASE_URL}/",
    ]

    for url in list_urls:
        log.info(f"Trying estimate list URL: {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await delay()

            # Check if we landed on a useful page
            if "login" in page.url.lower():
                log.warning(f"Redirected to login at {url}")
                continue

            log.info(f"Loaded: {page.url} | title: {await page.title()}")

            # Dump full page text and HTML for analysis
            page_text = await page.inner_text("body")
            log.info(f"Page text snippet: {page_text[:500]}")

            # Try to find estimate links/rows
            rows = await scrape_estimate_rows(page)
            if rows:
                estimates.extend(rows)
                log.info(f"Found {len(rows)} estimates on {url}")
                # Try pagination
                page_num = 2
                while True:
                    next_link = await page.query_selector("a[rel='next'], .pagination .next, a:has-text('Next')")
                    if not next_link:
                        break
                    await next_link.click()
                    await page.wait_for_load_state("domcontentloaded")
                    await delay()
                    more = await scrape_estimate_rows(page)
                    if not more:
                        break
                    estimates.extend(more)
                    log.info(f"Page {page_num}: {len(more)} more estimates")
                    page_num += 1
                break  # found estimates, stop trying URLs
        except Exception as e:
            log.warning(f"Failed {url}: {e}")
            continue

    # Deduplicate by estimate ID
    seen = set()
    unique = []
    for e in estimates:
        eid = e.get("id") or e.get("url")
        if eid and eid not in seen:
            seen.add(eid)
            unique.append(e)
    return unique


async def scrape_estimate_rows(page: Page) -> list[dict]:
    """Extract estimate rows from the current page."""
    rows = []

    # Strategy 1: look for table rows with estimate links
    table_rows = await page.query_selector_all("table tr")
    for row in table_rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 2:
            continue
        texts = [clean(await c.inner_text()) for c in cells]
        link_el = await row.query_selector("a[href]")
        href = await link_el.get_attribute("href") if link_el else ""
        if href and any(t for t in texts):
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            rows.append({"url": full_url, "cells": texts, "id": extract_id(href)})

    # Strategy 2: look for card-style estimate links
    if not rows:
        links = await page.query_selector_all("a[href*='estimate'], a[href*='Estimate'], a[href*='/e/']")
        for link in links:
            href = await link.get_attribute("href")
            text = clean(await link.inner_text())
            if href:
                full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
                rows.append({"url": full_url, "text": text, "id": extract_id(href)})

    return rows


def extract_id(href: str) -> str:
    # Extract numeric ID from URL like /estimates/12345 or /e/12345
    m = re.search(r"/(\d+)(?:/|$|\?)", href)
    return m.group(1) if m else href.split("/")[-1].split("?")[0]


# ─── Estimate Detail ──────────────────────────────────────────────

async def scrape_estimate_detail(page: Page, est_url: str, est_id: str, shop_id: int) -> dict:
    """Scrape all data from a single estimate detail page."""
    data: dict[str, Any] = {
        "estimate_id":   est_id,
        "source_url":    est_url,
        "scraped_at":    datetime.utcnow().isoformat(),
        "customer":      {},
        "vehicle":       {},
        "insurance":     {},
        "line_items":    [],
        "totals":        {},
        "supplements":   [],
        "photos":        [],
        "notes":         "",
        "raw_text":      "",
    }

    try:
        await page.goto(est_url, wait_until="domcontentloaded", timeout=30000)
        await delay()

        if "login" in page.url.lower():
            log.warning(f"Session expired at {est_url}")
            return data

        log.info(f"Scraping estimate {est_id}: {await page.title()}")

        # ── Raw full-page text (for analysis) ────────────────
        data["raw_text"] = clean(await page.inner_text("body"))

        # ── All form fields ───────────────────────────────────
        data["all_fields"] = await scrape_all_form_fields(page)

        # ── All tables ────────────────────────────────────────
        data["all_tables"] = await scrape_all_tables(page)

        # ── Customer ──────────────────────────────────────────
        data["customer"] = await scrape_customer(page)

        # ── Vehicle ───────────────────────────────────────────
        data["vehicle"] = await scrape_vehicle(page)

        # ── Insurance ─────────────────────────────────────────
        data["insurance"] = await scrape_insurance(page)

        # ── Line items (parts, labor, etc.) ───────────────────
        data["line_items"] = await scrape_line_items(page)

        # ── Totals ────────────────────────────────────────────
        data["totals"] = await scrape_totals(page)

        # ── Notes ─────────────────────────────────────────────
        data["notes"] = await scrape_notes(page)

        # ── Photos ────────────────────────────────────────────
        data["photos"] = await scrape_and_download_photos(page, est_id)

        # ── Supplements (look for supplement tabs/links) ──────
        data["supplements"] = await scrape_supplements(page, est_id)

        # ── Navigate sub-pages / tabs ─────────────────────────
        sub_data = await scrape_sub_pages(page, est_url, est_id)
        data.update(sub_data)

    except Exception as e:
        log.error(f"Error scraping estimate {est_id}: {e}")
        data["error"] = str(e)

    return data


async def scrape_all_form_fields(page: Page) -> dict:
    """Dump all input/select/textarea values on the page."""
    fields = {}
    try:
        inputs = await page.query_selector_all("input[name], select[name], textarea[name]")
        for el in inputs:
            name = await el.get_attribute("name") or await el.get_attribute("id") or ""
            tag  = await el.evaluate("el => el.tagName.toLowerCase()")
            if tag == "select":
                val = await el.evaluate("el => el.options[el.selectedIndex]?.text || el.value")
            elif tag == "input":
                type_ = (await el.get_attribute("type") or "text").lower()
                if type_ in ("checkbox", "radio"):
                    val = str(await el.evaluate("el => el.checked"))
                else:
                    val = await el.input_value()
            else:
                val = await el.evaluate("el => el.value")
            if name:
                fields[name] = clean(str(val))
    except Exception as e:
        log.debug(f"form fields error: {e}")
    return fields


async def scrape_all_tables(page: Page) -> list[dict]:
    """Dump every table on the page."""
    result = []
    try:
        tables = await page.query_selector_all("table")
        for i, tbl in enumerate(tables):
            html = await tbl.inner_html()
            rows = await table_to_dicts(page, f"table:nth-of-type({i+1})")
            caption_el = await tbl.query_selector("caption")
            caption = clean(await caption_el.inner_text()) if caption_el else f"table_{i}"
            result.append({"caption": caption, "rows": rows})
    except Exception as e:
        log.debug(f"tables error: {e}")
    return result


async def scrape_customer(page: Page) -> dict:
    c = {}
    # Common field name patterns for ProEstimator
    field_map = {
        "first_name":   ["#CustomerFirstName", "input[name*='FirstName']", "input[name*='first']"],
        "last_name":    ["#CustomerLastName",  "input[name*='LastName']",  "input[name*='last']"],
        "email":        ["#CustomerEmail",     "input[name*='Email']",    "input[type='email']"],
        "phone":        ["#CustomerPhone",     "input[name*='Phone']",    "input[name*='phone']"],
        "address":      ["#CustomerAddress",   "input[name*='Address']",  "input[name*='address']"],
        "city":         ["#CustomerCity",      "input[name*='City']"],
        "state":        ["#CustomerState",     "select[name*='State']"],
        "zip":          ["#CustomerZip",       "input[name*='Zip']"],
        "business":     ["#BusinessName",      "input[name*='Business']"],
    }
    for key, selectors in field_map.items():
        for sel in selectors:
            val = await safe_val(page, sel) or await safe_text(page, sel)
            if val:
                c[key] = val
                break
    return c


async def scrape_vehicle(page: Page) -> dict:
    v = {}
    field_map = {
        "vin":          ["#VIN", "input[name*='VIN']",   "input[name*='vin']"],
        "year":         ["#Year", "input[name*='Year']", "select[name*='Year']"],
        "make":         ["#Make", "input[name*='Make']", "select[name*='Make']"],
        "model":        ["#Model","input[name*='Model']","select[name*='Model']"],
        "trim":         ["#Style","input[name*='Style']","input[name*='Trim']"],
        "color":        ["#Color","input[name*='Color']","input[name*='color']"],
        "color_code":   ["#ColorCode","input[name*='ColorCode']"],
        "license":      ["#LicensePlate","input[name*='License']","input[name*='Plate']"],
        "license_state":["#LicenseState","select[name*='LicenseState']"],
        "mileage":      ["#Mileage","input[name*='Mileage']","input[name*='mileage']"],
        "production_date": ["#ProductionDate","input[name*='Production']"],
        "paint_code":   ["#PaintCode","input[name*='Paint']"],
    }
    for key, selectors in field_map.items():
        for sel in selectors:
            val = await safe_val(page, sel) or await safe_text(page, sel)
            if val:
                v[key] = val
                break
    return v


async def scrape_insurance(page: Page) -> dict:
    ins = {}
    field_map = {
        "company":      ["#InsuranceCompany","input[name*='InsuranceCompany']","input[name*='Company']"],
        "claim_number": ["#ClaimNumber","input[name*='Claim']"],
        "policy_number":["#PolicyNumber","input[name*='Policy']"],
        "adjuster":     ["#Adjuster","input[name*='Adjuster']"],
        "adjuster_phone":["#AdjusterPhone","input[name*='AdjusterPhone']"],
        "deductible":   ["#Deductible","input[name*='Deductible']"],
        "date_of_loss": ["#DateOfLoss","input[name*='Loss']","input[name*='DateOfLoss']"],
    }
    for key, selectors in field_map.items():
        for sel in selectors:
            val = await safe_val(page, sel) or await safe_text(page, sel)
            if val:
                ins[key] = val
                break
    return ins


async def scrape_line_items(page: Page) -> list[dict]:
    """Scrape parts/labor/other line items from estimate tables."""
    items = []

    # ProEstimator typically has separate sections for each line type
    section_selectors = [
        # table containing line items
        "table.estimate-lines",
        "table.line-items",
        "#estimate-table",
        "#lineItems",
        ".estimate-body table",
        "table",  # fallback: all tables
    ]

    for sel in section_selectors:
        tables = await page.query_selector_all(sel)
        for tbl in tables:
            rows_data = []
            rows = await tbl.query_selector_all("tr")
            if len(rows) < 2:
                continue

            # Get headers
            header_row = rows[0]
            headers = [clean(await h.inner_text()) for h in await header_row.query_selector_all("th, td")]

            # Check if this looks like a line items table
            header_text = " ".join(headers).lower()
            if not any(kw in header_text for kw in ["part", "labor", "description", "price", "qty", "hours", "amount"]):
                continue

            for row in rows[1:]:
                cells = await row.query_selector_all("td")
                if not cells:
                    continue
                vals = [clean(await c.inner_text()) for c in cells]
                if not any(vals):
                    continue
                item = {}
                for i, h in enumerate(headers):
                    item[h] = vals[i] if i < len(vals) else ""
                # Try to classify item type from row class or content
                row_class = await row.get_attribute("class") or ""
                item["_row_class"] = row_class
                rows_data.append(item)

            if rows_data:
                items.extend(rows_data)
                log.debug(f"Found {len(rows_data)} line items in a table")
                break  # use first matching table

    # Also try to grab items by section divs (some ProEstimator views)
    if not items:
        item_divs = await page.query_selector_all(".line-item, .estimate-row, [data-line-id]")
        for div in item_divs:
            text = clean(await div.inner_text())
            class_ = await div.get_attribute("class") or ""
            data_id = await div.get_attribute("data-line-id") or ""
            items.append({"raw_text": text, "class": class_, "data_id": data_id})

    return items


async def scrape_totals(page: Page) -> dict:
    """Scrape estimate totals (parts, labor, tax, total, deductible, net due)."""
    totals = {}
    # Common label → value patterns
    patterns = [
        ("parts_total",      ["Parts Total", "Parts", "Total Parts"]),
        ("labor_total",      ["Labor Total", "Labor", "Total Labor"]),
        ("paint_total",      ["Paint Total", "Paint", "Total Paint"]),
        ("sublet_total",     ["Sublet", "Other Charges"]),
        ("tax",              ["Tax", "Sales Tax"]),
        ("subtotal",         ["Subtotal", "Sub-Total"]),
        ("deductible",       ["Deductible", "Deduct."]),
        ("net_due",          ["Net Due", "Total Due", "Amount Due", "Balance Due"]),
        ("grand_total",      ["Grand Total", "Total", "Estimate Total"]),
        ("not_included",     ["Not Included", "N/I"]),
    ]

    page_text = await page.inner_text("body")
    for key, labels in patterns:
        for label in labels:
            # Look for label followed by dollar amount
            pattern = re.compile(
                re.escape(label) + r"[:\s]*\$?([\d,]+\.?\d*)",
                re.IGNORECASE
            )
            m = pattern.search(page_text)
            if m:
                totals[key] = to_float(m.group(1))
                break

    # Also try DOM-based extraction
    total_selectors = [
        (".totals-section", "div"),
        ("#estimate-totals", "div"),
        (".estimate-summary", "div"),
        ("tfoot", "tr"),
    ]
    for container_sel, child_tag in total_selectors:
        container = await page.query_selector(container_sel)
        if container:
            children = await container.query_selector_all(child_tag)
            for child in children:
                text = clean(await child.inner_text())
                for key, labels in patterns:
                    if key in totals:
                        continue
                    for label in labels:
                        if label.lower() in text.lower():
                            amounts = re.findall(r"\$?([\d,]+\.?\d{2})", text)
                            if amounts:
                                totals[key] = to_float(amounts[-1])

    return totals


async def scrape_notes(page: Page) -> str:
    for sel in ["#Notes", "textarea[name*='Note']", "#AdditionalInfo", ".estimate-notes"]:
        val = await safe_val(page, sel) or await safe_text(page, sel)
        if val:
            return val
    return ""


async def scrape_and_download_photos(page: Page, est_id: str) -> list[dict]:
    """Find and download all photos attached to the estimate."""
    photos = []
    photo_dir = PHOTOS_DIR / est_id
    photo_dir.mkdir(exist_ok=True)

    img_els = await page.query_selector_all("img[src*='photo'], img[src*='image'], img[src*='upload'], a[href*='photo'] img, .photo-gallery img, .damage-photo img")
    for i, img in enumerate(img_els):
        src = await img.get_attribute("src") or ""
        alt = clean(await img.get_attribute("alt") or "")
        if not src or "icon" in src.lower() or "logo" in src.lower() or "thumb" not in src.lower() and len(src) < 20:
            continue
        full_src = src if src.startswith("http") else f"{BASE_URL}{src}"
        # Swap thumbnail URL for full-size if possible
        full_size_src = re.sub(r"thumb[_-]?", "", full_src, flags=re.IGNORECASE)

        filename = f"{est_id}_photo_{i+1}{Path(full_src.split('?')[0]).suffix or '.jpg'}"
        local_path = str(photo_dir / filename)

        try:
            resp = await page.request.get(full_size_src or full_src)
            if resp.ok:
                content = await resp.body()
                with open(local_path, "wb") as f:
                    f.write(content)
                photos.append({"src": full_src, "local": local_path, "alt": alt})
                log.debug(f"Downloaded photo: {local_path}")
        except Exception as e:
            log.debug(f"Photo download failed {full_src}: {e}")
            photos.append({"src": full_src, "local": None, "alt": alt, "error": str(e)})

    return photos


async def scrape_supplements(page: Page, est_id: str) -> list[dict]:
    """Look for supplement entries on the estimate."""
    supplements = []
    try:
        # Look for supplement links or tabs
        supp_links = await page.query_selector_all(
            "a[href*='supplement'], a[href*='Supplement'], "
            ".supplement-tab, [data-tab*='supplement'], "
            "a:has-text('Supplement')"
        )
        for link in supp_links:
            href = await link.get_attribute("href") or ""
            text = clean(await link.inner_text())
            supplements.append({"link_text": text, "href": href})
    except Exception as e:
        log.debug(f"Supplement scrape error: {e}")
    return supplements


async def scrape_sub_pages(page: Page, base_url: str, est_id: str) -> dict:
    """Navigate to sub-tabs (Photos, Supplements, Payments, etc.) and scrape those too."""
    sub_data = {}

    # Find all nav tabs / sub-page links
    tab_links = await page.query_selector_all(
        ".nav-tabs a, .tab-list a, .estimate-nav a, "
        "ul.tabs li a, [role='tab'], .menu-item a"
    )

    for link in tab_links:
        tab_text = clean(await link.inner_text()).lower()
        href = await link.get_attribute("href") or ""

        if not tab_text or tab_text in ("", "home", "dashboard"):
            continue

        # Click the tab if it's in-page, otherwise navigate
        try:
            if href.startswith("#") or not href:
                await link.click()
                await page.wait_for_load_state("domcontentloaded")
                await delay()
                tab_content = clean(await page.inner_text("body"))
                sub_data[f"tab_{tab_text}"] = tab_content[:5000]
            elif href and (base_url.split("?")[0] in href or href.startswith("/")):
                # Same-domain sub-page
                full_href = href if href.startswith("http") else f"{BASE_URL}{href}"
                await page.goto(full_href, wait_until="domcontentloaded", timeout=20000)
                await delay()
                fields = await scrape_all_form_fields(page)
                tables = await scrape_all_tables(page)
                text   = clean(await page.inner_text("body"))
                sub_data[f"subpage_{tab_text}"] = {
                    "url": full_href,
                    "fields": fields,
                    "tables": tables,
                    "text_snippet": text[:3000],
                }
                # Go back to estimate
                await page.goto(base_url, wait_until="domcontentloaded", timeout=20000)
                await delay()
        except Exception as e:
            log.debug(f"Sub-page tab '{tab_text}' error: {e}")

    return sub_data


# ─── Rate Profiles ────────────────────────────────────────────────

async def scrape_rate_profiles(context: BrowserContext, shop_id: int) -> list[dict]:
    """Scrape labor rate profiles from shop settings."""
    profiles = []
    page = await context.new_page()
    profile_urls = [
        f"{BASE_URL}/{shop_id}/rateprofiles",
        f"{BASE_URL}/rateprofiles?shop={shop_id}",
        f"{BASE_URL}/settings/rates",
        f"{BASE_URL}/{shop_id}/settings",
    ]
    for url in profile_urls:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await delay()
            if "login" in page.url.lower():
                break
            tables = await scrape_all_tables(page)
            fields = await scrape_all_form_fields(page)
            text   = await page.inner_text("body")
            if tables or fields:
                profiles.append({
                    "url": url,
                    "tables": tables,
                    "fields": fields,
                    "raw_text": text[:3000],
                })
                log.info(f"Rate profile data scraped from {url}")
                break
        except Exception as e:
            log.debug(f"Rate profile URL {url}: {e}")
    await page.close()
    return profiles


# ─── Save output ──────────────────────────────────────────────────

def save_json(data: Any, filename: str):
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(data, indent=2, default=str))
    log.info(f"JSON saved: {path}")
    return path


def save_csv(estimates: list[dict]):
    path = OUTPUT_DIR / "estimates_summary.csv"
    if not estimates:
        return
    # Flatten top-level fields for CSV
    rows = []
    for e in estimates:
        row = {
            "estimate_id": e.get("estimate_id", ""),
            "source_url":  e.get("source_url", ""),
            "scraped_at":  e.get("scraped_at", ""),
            # Customer
            **{f"customer_{k}": v for k, v in e.get("customer", {}).items()},
            # Vehicle
            **{f"vehicle_{k}": v for k, v in e.get("vehicle", {}).items()},
            # Insurance
            **{f"insurance_{k}": v for k, v in e.get("insurance", {}).items()},
            # Totals
            **{f"total_{k}": v for k, v in e.get("totals", {}).items()},
            "notes": e.get("notes", ""),
            "num_line_items": len(e.get("line_items", [])),
            "num_photos":     len(e.get("photos", [])),
        }
        rows.append(row)

    all_keys = list(dict.fromkeys(k for r in rows for k in r.keys()))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"CSV saved: {path}")


# ─── Main ─────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="ProEstimator Web-Est Scraper")
    parser.add_argument("--shop-id",       type=int, default=53288, help="Shop ID (default: 53288)")
    parser.add_argument("--max-estimates", type=int, default=0,     help="Max estimates to scrape (0 = all)")
    parser.add_argument("--headless",      action="store_true",      help="Run browser headless (default: headed)")
    parser.add_argument("--debug",         action="store_true",      help="Debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = f"proestimator_full_{timestamp}.json"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=args.headless,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
        )
        context = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        # Stealth: remove webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        # ── Auth ──────────────────────────────────────────────
        authenticated = await authenticate(context)
        if not authenticated:
            log.error("Exiting: authentication required")
            await browser.close()
            sys.exit(1)

        # ── Estimate list ─────────────────────────────────────
        log.info(f"Fetching estimate list for shop {args.shop_id}...")
        page = await context.new_page()
        estimate_list = await get_estimate_list(page, args.shop_id)
        await page.close()

        log.info(f"Found {len(estimate_list)} estimates total")

        if args.max_estimates:
            estimate_list = estimate_list[:args.max_estimates]
            log.info(f"Capped at {args.max_estimates} estimates")

        # ── Rate profiles ─────────────────────────────────────
        log.info("Scraping rate profiles...")
        rate_profiles = await scrape_rate_profiles(context, args.shop_id)

        # ── Estimate details ──────────────────────────────────
        all_estimates = []
        page = await context.new_page()

        for i, est in enumerate(estimate_list):
            est_url = est.get("url", "")
            est_id  = est.get("id", str(i + 1))
            if not est_url:
                continue
            log.info(f"[{i+1}/{len(estimate_list)}] Scraping estimate {est_id}")
            detail = await scrape_estimate_detail(page, est_url, est_id, args.shop_id)
            detail["list_row"] = est  # attach list-level metadata
            all_estimates.append(detail)

            # Incremental save every 10 estimates
            if (i + 1) % 10 == 0:
                save_json(all_estimates, f"proestimator_partial_{timestamp}.json")
                log.info(f"Partial save: {i+1} estimates")

        await page.close()

        # ── Final output ──────────────────────────────────────
        full_output = {
            "shop_id":       args.shop_id,
            "scraped_at":    timestamp,
            "total_scraped": len(all_estimates),
            "rate_profiles": rate_profiles,
            "estimates":     all_estimates,
        }

        save_json(full_output, output_file)
        save_csv(all_estimates)

        log.info("=" * 60)
        log.info(f"Scrape complete! {len(all_estimates)} estimates scraped.")
        log.info(f"JSON: {OUTPUT_DIR / output_file}")
        log.info(f"CSV:  {OUTPUT_DIR / 'estimates_summary.csv'}")
        log.info(f"Photos: {PHOTOS_DIR}/")
        log.info("=" * 60)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
