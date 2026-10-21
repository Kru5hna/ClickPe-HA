-- =============================================================================
-- DATABASE SCHEMA for the Loan Eligibility Engine
-- =============================================================================
-- This file runs automatically when Postgres starts for the first time
-- (Docker mounts it into /docker-entrypoint-initdb.d/).
--
-- THREE TABLES:
--   1. users          — people who uploaded their info via CSV
--   2. loan_products  — loan offers crawled from bank websites (Workflow A)
--   3. matches        — which user qualifies for which loan (Workflow B)
-- =============================================================================


-- table 1
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    monthly_income INTEGER NOT NULL,
    credit_score INTEGER NOT NULL,
    employment_status VARCHAR(50) NOT NULL,
    age INTEGER NOT NULL,
    batch_id UUID,                          -- links all users from one CSV upload
    created_at TIMESTAMP DEFAULT NOW()
);


CREATE INDEX idx_users_income ON users(monthly_income);
CREATE INDEX idx_users_credit ON users(credit_score);
CREATE INDEX idx_users_batch ON users(batch_id);


-- table 2
CREATE TABLE loan_products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL UNIQUE,  -- UNIQUE required for ON CONFLICT in Workflow A
    provider VARCHAR(255) NOT NULL,
    interest_rate DECIMAL(5,2),
    min_income INTEGER DEFAULT 0,
    max_income INTEGER DEFAULT 99999999,     -- NULL-safe: default to a huge number
    min_credit_score INTEGER DEFAULT 0,
    max_credit_score INTEGER DEFAULT 900,
    employment_types TEXT[] DEFAULT '{}',     -- Postgres array of strings
    min_age INTEGER DEFAULT 18,
    max_age INTEGER DEFAULT 70,
    source_url TEXT,
    last_crawled TIMESTAMP DEFAULT NOW()
);


-- table 3
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES loan_products(product_id) ON DELETE CASCADE,
    match_score DECIMAL(3,2) DEFAULT 1.00,
    match_reason TEXT,
    batch_id UUID,
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),

    -- UNIQUE CONSTRAINT: Prevents duplicate matches.
    -- Without this, re-running Workflow B would create duplicate rows.
    UNIQUE(user_id, product_id)
);

-- INDEX: Workflow C queries "give me all matches for batch X that haven't been
-- notified yet" — this index makes that query fast.
CREATE INDEX idx_matches_batch_notified ON matches(batch_id, notified);
