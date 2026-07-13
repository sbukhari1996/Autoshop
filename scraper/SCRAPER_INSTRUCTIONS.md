# ProEstimator Scraper — Setup & Usage

This script scrapes all data from your ProEstimator Web-Est account
(https://proestimator.web-est.com/53288) and exports it as JSON + CSV so
Claude can use it to build your shop management replica.

---

## Prerequisites

```bash
pip install playwright
playwright install chromium
# OR if running inside Docker:
# playwright install-deps chromium
```

---

## Auth Method 1 — Browser Cookies (Recommended, No Password Needed)

### Step 1: Export your session cookies

1. Log into https://proestimator.web-est.com in Chrome
2. Install the **"EditThisCookie"** Chrome extension  
   (or use "Cookie-Editor" — any extension that exports cookies as JSON)
3. On any ProEstimator page, open the extension → click **Export** (copy icon)
4. Paste the JSON into a file called `my_cookies.json` in the `scraper/` folder

### Step 2: Set environment variable

```bash
export PROEST_COOKIES_JSON="$(cat scraper/my_cookies.json)"
```

### Step 3: Run

```bash
cd scraper
python proestimator_scraper.py --shop-id 53288
```

---

## Auth Method 2 — Email + Password

```bash
export PROEST_EMAIL="your@email.com"
export PROEST_PASSWORD="yourpassword"

cd scraper
python proestimator_scraper.py --shop-id 53288
```

> The first time you run with email/password the script will save your session
> cookies to `scraped_data/session_cookies.json` so you can reuse them next time.

---

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--shop-id` | 53288 | Your ProEstimator shop ID |
| `--max-estimates` | 0 (all) | Limit number of estimates (useful for testing) |
| `--headless` | off | Run browser without a visible window |
| `--debug` | off | Verbose logging |

**Test run (first 5 estimates only):**
```bash
python proestimator_scraper.py --shop-id 53288 --max-estimates 5
```

**Full scrape, no browser window:**
```bash
python proestimator_scraper.py --shop-id 53288 --headless
```

---

## Output Files

| File | Contents |
|------|----------|
| `scraped_data/proestimator_full_<timestamp>.json` | Complete data dump (all estimates, line items, vehicles, customers, photos, totals) |
| `scraped_data/estimates_summary.csv` | One row per estimate (good for spreadsheet review) |
| `scraped_data/photos/<estimate_id>/` | Downloaded damage photos per estimate |
| `scraped_data/session_cookies.json` | Saved session cookies (email/password mode only) |

---

## What Gets Scraped

- **Estimates** — all estimates in your shop
- **Customers** — name, email, phone, address
- **Vehicles** — VIN, year, make, model, color code, license plate, mileage
- **Insurance** — company, claim #, policy #, adjuster, deductible, date of loss
- **Line items** — parts, labor hours, paint, sublet, other charges
- **Totals** — parts total, labor total, tax, deductible, net due, grand total
- **Notes** — estimate notes
- **Photos** — downloaded locally
- **Supplements** — supplement history links
- **Rate profiles** — your labor rates

---

## After Scraping

Once you have `proestimator_full_<timestamp>.json`, give it to Claude with this prompt:

```
Here is a full data export from my ProEstimator account: [attach JSON file]
Build me a complete shop management system based on this data structure.
See the CLAUDE.md and skills/ files in the Autoshop repo for architecture.
```

---

## Troubleshooting

**"Authentication failed"**  
→ Make sure your cookies haven't expired. Log in again and re-export.

**"Redirected to login"**  
→ The `.ASPXAUTH` or session cookie may be missing. Export ALL cookies from
the ProEstimator domain, not just the visible ones.

**Empty estimate list**  
→ The scraper tries several URL patterns. Run with `--debug` to see what
URL the site is actually using, then report it.

**Rate limit / CAPTCHA**  
→ Increase delays in the script: change `DELAY_MIN = 3.0` and `DELAY_MAX = 6.0`.
