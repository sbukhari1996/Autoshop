# AutoEst Pro — Auto Collision Estimating Platform

## Quick Start

```bash
# 1. Clone / open the project folder
cd autoest-pro

# 2. Copy env file
cp .env.example .env

# 3. Build and start all 4 containers
docker-compose up --build

# 4. Open the app
# Frontend:  http://localhost
# API docs:  http://localhost:8000/docs
# Database:  localhost:5432 (user: autoest / pw: autoest_secret)
```

## Container Map

| Container          | Port | Purpose                          |
|--------------------|------|----------------------------------|
| autoest_db         | 5432 | PostgreSQL 16                    |
| autoest_api        | 8000 | FastAPI backend                  |
| autoest_scraper    | —    | Playwright background worker     |
| autoest_frontend   | 80   | Nginx serving the JS UI          |

## Workflow

1. **New Estimate** → fill Customer info → Save
2. **Vehicle** tab → Enter VIN → Decode → Save
3. **Add Parts** → click category → use quick-add or "Add Manual"
4. **Insurance** tab → fill claim details → Save
5. **Images** → drag/drop damage photos
6. **Export PDF** → downloads the Web-Est-style estimate

## Scraper

Parts price lookup happens automatically when you click "Lookup" on a part number.
VIN diagram downloads are queued via "Download Diagrams for VIN" in the Add Parts tab.
The scraper worker polls every 10 seconds for pending jobs.

## Labor Rates

Default rates (from `api/data/labor_rates.json`):
- Body: $48/hr  
- Paint: $48/hr  
- Mechanical: $65/hr  
- Frame/Structure: $55/hr  
- Paint Supplies: $28/hr  
- Tax: 7%

Override per-estimate via the Rate Profile editor.
