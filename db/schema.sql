-- users table
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    name VARCHAR(255),
    email VARCHAR(255),
    monthly_income INTEGER,
    credit_score INTEGER,
    employment_status VARCHAR(50),
    age INTEGER,
    batch_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- loan_products table  
CREATE TABLE loan_products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255),
    provider VARCHAR(255),
    interest_rate DECIMAL(5,2),
    min_income INTEGER,
    max_income INTEGER,
    min_credit_score INTEGER,
    max_credit_score INTEGER,
    employment_types TEXT[],
    min_age INTEGER,
    max_age INTEGER,
    source_url TEXT,
    last_crawled TIMESTAMP DEFAULT NOW()
);

-- matches table
CREATE TABLE matches (
    match_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    product_id INTEGER REFERENCES loan_products(product_id),
    match_score DECIMAL(3,2),
    match_reason TEXT,
    batch_id UUID,
    notified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
