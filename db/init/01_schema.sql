-- AutoEst Pro - PostgreSQL Schema
-- Mirrors Web-Est data model extracted from UI + PDF analysis

-- ─── Extensions ──────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Shops ───────────────────────────────────────────────────
CREATE TABLE shops (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    address     TEXT,
    city        TEXT,
    state       TEXT,
    zip         TEXT,
    phone       TEXT,
    email       TEXT,
    logo_path   TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Default shop (Master Craft)
INSERT INTO shops (name, address, city, state, zip, phone, email)
VALUES ('Master Craft Auto Repair & Collision', '38-21 23rd St.', 'Long Island', 'NY', '11101',
        '(718) 578-4563', 'shop@mastercraftautony.com');

-- ─── Customers ────────────────────────────────────────────────
CREATE TABLE customers (
    id                  SERIAL PRIMARY KEY,
    shop_id             INTEGER REFERENCES shops(id) ON DELETE CASCADE DEFAULT 1,
    first_name          TEXT NOT NULL,
    last_name           TEXT NOT NULL,
    email               TEXT,
    secondary_email     TEXT,
    phone1              TEXT,
    phone1_ext          TEXT,
    phone1_type         TEXT,
    phone2              TEXT,
    phone2_ext          TEXT,
    phone2_type         TEXT,
    phone3              TEXT,
    phone3_ext          TEXT,
    phone3_type         TEXT,
    address1            TEXT,
    address2            TEXT,
    city                TEXT,
    state               TEXT,
    zip                 TEXT,
    business_name       TEXT,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Vehicles ─────────────────────────────────────────────────
CREATE TABLE vehicles (
    id                      SERIAL PRIMARY KEY,
    vin                     TEXT UNIQUE,
    year                    INTEGER,
    make                    TEXT,
    model                   TEXT,
    trim                    TEXT,
    body_type               TEXT,
    paint_type              TEXT,        -- e.g. "2 Stage", "3 Stage"
    drive_type              TEXT,        -- AWD, FWD, RWD, 4WD
    engine                  TEXT,
    transmission            TEXT,
    production_year         INTEGER,
    production_month        INTEGER,
    primary_color_code      TEXT,        -- e.g. "R569M"
    primary_color_name      TEXT,        -- e.g. "Radiant Red"
    color_interior          TEXT,
    second_paint_code       TEXT,
    second_color_name       TEXT,
    license_plate           TEXT,
    license_state           TEXT,
    accessories             JSONB DEFAULT '[]',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Rate Profiles ─────────────────────────────────────────────
CREATE TABLE rate_profiles (
    id                      SERIAL PRIMARY KEY,
    shop_id                 INTEGER REFERENCES shops(id) DEFAULT 1,
    name                    TEXT NOT NULL DEFAULT 'New Rate Profile',
    description             TEXT,
    -- Labor rates ($/hr)
    body_rate               NUMERIC(8,2) DEFAULT 48.00,
    paint_rate              NUMERIC(8,2) DEFAULT 48.00,
    mechanical_rate         NUMERIC(8,2) DEFAULT 65.00,
    frame_rate              NUMERIC(8,2) DEFAULT 55.00,
    structure_rate          NUMERIC(8,2) DEFAULT 55.00,
    electrical_rate         NUMERIC(8,2) DEFAULT 65.00,
    aluminum_rate           NUMERIC(8,2) DEFAULT 48.00,
    cleanup_rate            NUMERIC(8,2) DEFAULT 48.00,
    other_rate              NUMERIC(8,2) DEFAULT 48.00,
    glass_rate              NUMERIC(8,2) DEFAULT 48.00,
    -- Supplies rates ($/hr)
    paint_supply_rate       NUMERIC(8,2) DEFAULT 28.00,
    body_supply_rate        NUMERIC(8,2) DEFAULT 0.00,
    -- Paint finish settings
    overlap_adj_hrs         NUMERIC(5,2) DEFAULT 0.4,
    overlap_non_adj_hrs     NUMERIC(5,2) DEFAULT 0.2,
    allow_deductions        BOOLEAN DEFAULT TRUE,
    paint_2stage_1st_pct    NUMERIC(5,2) DEFAULT 40.0,
    paint_2stage_add_pct    NUMERIC(5,2) DEFAULT 20.0,
    paint_3stage_1st_pct    NUMERIC(5,2) DEFAULT 70.0,
    paint_3stage_add_pct    NUMERIC(5,2) DEFAULT 40.0,
    blend_pct               NUMERIC(5,2) DEFAULT 50.0,
    blend_3stage_pct        NUMERIC(5,2) DEFAULT 70.0,
    underside_pct           NUMERIC(5,2) DEFAULT 50.0,
    edging_hrs              NUMERIC(5,2) DEFAULT 0.5,
    clearcoat_hrs           NUMERIC(5,2) DEFAULT 3.5,
    -- Parts markup/discount
    lkq_markup_pct          NUMERIC(5,2) DEFAULT 25.0,
    aftermarket_markup_pct  NUMERIC(5,2) DEFAULT 0.0,
    reman_markup_pct        NUMERIC(5,2) DEFAULT 0.0,
    -- Tax
    tax_rate_pct            NUMERIC(5,2) DEFAULT 7.0,
    -- Credit card
    cc_fee_pct              NUMERIC(5,2) DEFAULT 0.0,
    apply_cc_fee            BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO rate_profiles (name, description) VALUES ('Default Profile', 'PE Default Rate Profile');

-- ─── Insurance Companies ──────────────────────────────────────
CREATE TABLE insurance_companies (
    id      SERIAL PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

INSERT INTO insurance_companies (name) VALUES
    ('Erie Insurance Exchange'),
    ('State Farm'),
    ('GEICO'),
    ('Allstate'),
    ('Progressive'),
    ('USAA'),
    ('Nationwide'),
    ('Travelers'),
    ('Liberty Mutual'),
    ('Farmers');

-- ─── Estimates ────────────────────────────────────────────────
CREATE TABLE estimates (
    id                      SERIAL PRIMARY KEY,
    shop_id                 INTEGER REFERENCES shops(id) DEFAULT 1,
    customer_id             INTEGER REFERENCES customers(id),
    vehicle_id              INTEGER REFERENCES vehicles(id),
    rate_profile_id         INTEGER REFERENCES rate_profiles(id) DEFAULT 1,
    estimate_number         INTEGER NOT NULL DEFAULT 1,
    status                  TEXT DEFAULT 'Open',   -- Open, Closed, Supplement
    estimator_name          TEXT DEFAULT 'Syed Bukhari',
    inspection_date         DATE,
    assignment_date         DATE,
    repair_days             INTEGER DEFAULT 0,
    repair_hours_per_day    INTEGER DEFAULT 5,
    purchase_order_number   TEXT,
    repair_notes            TEXT,
    estimate_description    TEXT,
    first_poi               TEXT,   -- Point of Impact 1
    second_poi              TEXT,   -- Point of Impact 2
    -- Computed totals (denormalized for fast PDF generation)
    total_body_labor_hrs    NUMERIC(8,2) DEFAULT 0,
    total_paint_labor_hrs   NUMERIC(8,2) DEFAULT 0,
    total_paint_supply_hrs  NUMERIC(8,2) DEFAULT 0,
    total_parts_oem         NUMERIC(10,2) DEFAULT 0,
    total_parts_other       NUMERIC(10,2) DEFAULT 0,
    total_nontaxed          NUMERIC(10,2) DEFAULT 0,
    total_taxed             NUMERIC(10,2) DEFAULT 0,
    taxable_amount          NUMERIC(10,2) DEFAULT 0,
    tax_amount              NUMERIC(10,2) DEFAULT 0,
    non_taxable_amount      NUMERIC(10,2) DEFAULT 0,
    grand_total             NUMERIC(10,2) DEFAULT 0,
    deductible              NUMERIC(10,2) DEFAULT 0,
    net_total_due           NUMERIC(10,2) DEFAULT 0,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Insurance (per estimate) ─────────────────────────────────
CREATE TABLE insurance (
    id                          SERIAL PRIMARY KEY,
    estimate_id                 INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    policy_number               TEXT,
    claim_number                TEXT,
    coverage_type               TEXT,   -- Comprehensive, Collision, Liability
    deductible                  NUMERIC(10,2) DEFAULT 0,
    date_of_loss                DATE,
    company_id                  INTEGER REFERENCES insurance_companies(id),
    company_name_override       TEXT,   -- if not in list
    agent_first_name            TEXT,
    agent_last_name             TEXT,
    agent_phone                 TEXT,
    agent_fax                   TEXT,
    agent_email                 TEXT,
    adjuster_first_name         TEXT,
    adjuster_last_name          TEXT,
    adjuster_phone              TEXT,
    adjuster_phone_ext          TEXT,
    adjuster_fax                TEXT,
    adjuster_email              TEXT,
    claim_rep_first_name        TEXT,
    claim_rep_last_name         TEXT,
    claim_rep_phone             TEXT,
    claim_rep_phone_ext         TEXT,
    claim_rep_fax               TEXT,
    claim_rep_email             TEXT,
    claimant_same_as_owner      BOOLEAN DEFAULT TRUE,
    insured_same_as_owner       BOOLEAN DEFAULT TRUE,
    print_insured               BOOLEAN DEFAULT FALSE
);

-- ─── Estimate Lines ───────────────────────────────────────────
CREATE TABLE estimate_lines (
    id                  SERIAL PRIMARY KEY,
    estimate_id         INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    supplement_id       INTEGER DEFAULT 0,   -- 0 = base estimate
    line_number         INTEGER NOT NULL,
    section             TEXT NOT NULL,       -- FRONT BUMPER, GRILLE, FRONT LAMPS, etc.
    operation           TEXT NOT NULL,       -- Replace, R&I, Repair, Refinish, Overhaul, Align, Other, None
    description         TEXT NOT NULL,
    part_number         TEXT,
    part_price          NUMERIC(10,2) DEFAULT 0,
    qty                 INTEGER DEFAULT 1,
    source              TEXT DEFAULT 'OEM',  -- OEM, After, LKQ, Reman
    -- Labor hours by type
    body_labor_hrs      NUMERIC(5,2) DEFAULT 0,
    paint_labor_hrs     NUMERIC(5,2) DEFAULT 0,
    refinish_hrs        NUMERIC(5,2) DEFAULT 0,
    clearcoat_hrs       NUMERIC(5,2) DEFAULT 0,
    underside_hrs       NUMERIC(5,2) DEFAULT 0,
    -- Flags
    labor_included      BOOLEAN DEFAULT FALSE,  -- "Included" instead of hours
    is_taxable          BOOLEAN DEFAULT TRUE,
    oh_flag             BOOLEAN DEFAULT FALSE,  -- Overlap/overlap deduction
    notes               TEXT,
    -- Computed line total
    line_total          NUMERIC(10,2) DEFAULT 0,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_estimate_lines_estimate ON estimate_lines(estimate_id);
CREATE INDEX idx_estimate_lines_section ON estimate_lines(section);

-- ─── Estimate Images ──────────────────────────────────────────
CREATE TABLE estimate_images (
    id              SERIAL PRIMARY KEY,
    estimate_id     INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    file_name       TEXT,
    uploaded_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Scraped Parts Cache ──────────────────────────────────────
CREATE TABLE scraped_parts (
    id              SERIAL PRIMARY KEY,
    part_number     TEXT NOT NULL,
    description     TEXT,
    msrp            NUMERIC(10,2),
    source_url      TEXT,
    dealer_name     TEXT,
    make            TEXT,
    model           TEXT,
    year            INTEGER,
    svg_diagram_url TEXT,
    svg_local_path  TEXT,
    scraped_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(part_number, dealer_name)
);

CREATE INDEX idx_scraped_parts_pn ON scraped_parts(part_number);

-- ─── Scrape Jobs Queue ────────────────────────────────────────
CREATE TABLE scrape_jobs (
    id              SERIAL PRIMARY KEY,
    job_type        TEXT NOT NULL,  -- 'part', 'vin_diagram'
    payload         JSONB NOT NULL, -- {part_number, make, model, year} or {vin}
    status          TEXT DEFAULT 'pending',  -- pending, running, done, failed
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

-- ─── Supplements ──────────────────────────────────────────────
CREATE TABLE supplements (
    id              SERIAL PRIMARY KEY,
    estimate_id     INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    supplement_num  INTEGER NOT NULL DEFAULT 1,
    caption         TEXT DEFAULT 'Supplement 1',
    total           NUMERIC(10,2) DEFAULT 0,
    lines_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Helper: auto-update updated_at ──────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_estimates_updated
    BEFORE UPDATE ON estimates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_customers_updated
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
