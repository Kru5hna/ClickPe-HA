# 💰 ClickPe — Loan Eligibility Engine

An automated system that ingests user data via CSV, discovers personal loan products from public websites, matches users to eligible products using a multi-stage optimized pipeline, and notifies them via email.

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                          LOAN ELIGIBILITY ENGINE                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐                   │
│  │  Upload UI  │────▶│ Lambda:      │────▶│    S3        │                   │
│  │ (index.html)│     │ Presigned URL│     │  Bucket      │                   │
│  └─────────────┘     └──────────────┘     └──────┬───────┘                   │
│                                                  │ S3 Event                  │
│                                                  ▼                           │
│                                            ┌──────────────┐                  │
│                                            │ Lambda:      │                  │
│                                            │ CSV Processor│                  │
│                                            └──────┬───────┘                  │
│                                                   │ Webhook                  │
│  ┌────────────────────────────────────────────────┼─────────────────────┐    │
│  │  n8n (Docker)                                  ▼                     │    │
│  │  ┌──────────────┐  ┌──────────────────┐  ┌──────────────┐            │    │
│  │  │ Workflow A   │  │   Workflow B     │  │ Workflow C   │            │    │
│  │  │ Loan Crawler │  │ Matching Engine  │  │ Email Notify │            │    │
│  │  │  (Daily)     │  │ ┌──────────────┐ │  │              │            │    │
│  │  │              │  │ │Stage1: SQL   │ │  │   ┌─────┐    │            │    │
│  │  │ HTTP Request │  │ │Pre-Filter    │ │  │   │ SES │    │            │    │
│  │  │ HTML Extract │  │ ├──────────────┤ │  │   └─────┘    │            │    │
│  │  │ Code Node    │  │ │Stage2: Rule  │ │  │              │            │    │
│  │  │              │  │ │Engine (JS)   │ │  └──────────────┘            │    │
│  │  │              │  │ ├──────────────┤ │                              │    │
│  │  │              │  │ │Stage3: LLM   │ │                              │    │
│  │  │              │  │ │(Gemini API)  │ │                              │    │
│  │  │              │  │ └──────────────┘ │                              │    │
│  │  └──────┬───────┘  └────────┬─────────┘                              │    │
│  │         │                   │                                        │    │
│  └─────────┼───────────────────┼────────────────────────────────────────┘    │
│            │                   │                                             │
│            ▼                   ▼                                             │
│      ┌─────────────────────────────────┐                                     │
│      │     PostgreSQL (Docker)         │                                     │
│      │  ┌─────────┐ ┌──────────────┐   │                                     │
│      │  │ users   │ │loan_products │   │                                     │
│      │  └─────────┘ └──────────────┘   │                                     │
│      │  ┌──────────┐                   │                                     │
│      │  │ matches  │                   │                                     │
│      │  └──────────┘                   │                                     │
│      └─────────────────────────────────┘                                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

- **Docker Desktop** (for running n8n + PostgreSQL)
- **Node.js 18+** (for Serverless Framework)
- **Python 3.11+** (for Lambda functions)
- **AWS CLI** configured with credentials
- **Serverless Framework** (`npm install -g serverless`)

## 🚀 Setup & Deployment

### Step 1: Clone and Start Local Infrastructure

```bash
# Clone the repository
git clone <repo-url>
cd ClickPe

# Start PostgreSQL and n8n using Docker Compose
docker compose up -d

# Verify containers are running
docker compose ps

# PostgreSQL will be available at: localhost:5432
# n8n will be available at:       http://localhost:5678
```

### Step 2: Configure n8n Credentials

1. Open **http://localhost:5678** in your browser
2. Create an account (first-time setup)
3. Go to **Settings → Credentials → Add Credential**:

   **PostgreSQL Credential:**
   | Field | Value |
   |-------|-------|
   | Host | `postgres` (Docker service name) |
   | Port | `5432` |
   | Database | `clickpe_db` |
   | User | `clickpe_user` |
   | Password | `clickpe_pass` |

   **AWS Credential (for SES):**
   | Field | Value |
   |-------|-------|
   | Access Key ID | Your AWS access key |
   | Secret Access Key | Your AWS secret key |
   | Region | `ap-south-1` |

### Step 3: Import n8n Workflows

1. In n8n, click **+ Add Workflow**
2. Click the **⋮** menu → **Import from File**
3. Import each JSON file from `n8n-workflows/`:
   - `workflow_a_crawler.json` — Loan Product Discovery
   - `workflow_b_matching.json` — User-Loan Matching
   - `workflow_c_notification.json` — Email Notifications
4. In each workflow, update the **Postgres node credentials** to use your configured credential
5. Activate each workflow

### Step 4: Deploy AWS Resources (Optional — for public deployment)

```bash
# Install dependencies
cd lambda/csv_processor
pip install -r requirements.txt -t .
cd ../..

# Deploy to AWS
serverless deploy

# Note the API Gateway URL from the output — you'll need it for the frontend
```

### Step 5: Configure the Frontend

1. Open `frontend/index.html` in a browser
2. If using local testing: set the API endpoint to `http://localhost:3000/dev/upload-url`
3. If deployed to AWS: paste the API Gateway URL from Step 4

### Step 6: Set Up AWS SES (for email notifications)

1. Go to **AWS Console → SES → Verified Identities**
2. Verify your sender email address
3. Verify test recipient addresses (in sandbox mode, both must be verified):
   - `yourname+one@gmail.com`
   - `yourname+two@gmail.com`
4. Update the sender email in `workflow_c_notification.json`

### Step 7: Set Up Tunnel (for AWS → local n8n communication)

```bash
# Install ngrok
# Download from https://ngrok.com/download

# Start tunnel to n8n
ngrok http 5678

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Set it as the N8N_WEBHOOK_URL in serverless.yml or Lambda environment variables
```

## 📊 Database Schema

| Table           | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `users`         | Stores user profiles from uploaded CSV files     |
| `loan_products` | Loan offers discovered by Workflow A (crawler)   |
| `matches`       | User-product eligibility matches from Workflow B |

## 🔧 Design Decisions

### 1. S3 Presigned URL Upload Pattern

Instead of uploading the CSV through API Gateway → Lambda (which has a 6MB payload limit and 30-second timeout), the frontend:

1. Requests a presigned URL from a lightweight Lambda
2. Uploads the file directly to S3 (no size limits)
3. S3 triggers the processing Lambda via event notification

This is the **event-driven, scalable pattern** recommended for production workloads.

### 2. Web Crawling Strategy

Workflow A crawls 3 major Indian bank websites (Bajaj Finserv, HDFC Bank, ICICI Bank) daily using n8n's HTTP Request node. The HTML is fetched and product data is normalized in a Code node. We use a fallback data approach since bank websites can change their layouts anytime — the architecture (schedule → crawl → extract → store) is what matters.

### 3. Optimization Treasure Hunt — 3-Stage Matching Pipeline

This is the most critical design decision. The naive approach (LLM for every pair) would be:

- **10,000 users × 10 products = 100,000 LLM calls**
- At ~0.6s per call = **~16.7 hours**
- At $0.001 per call = **$100+**

Our 3-stage pipeline:

| Stage             | Method                             | Pairs In | Pairs Out | Time       |
| ----------------- | ---------------------------------- | -------- | --------- | ---------- |
| 1. SQL Pre-Filter | PostgreSQL JOIN with range checks  | 100,000  | ~5,000    | <1 second  |
| 2. Rule Engine    | JavaScript in n8n Code node        | ~5,000   | ~2,000    | <1 second  |
| 3. LLM (Gemini)   | Batched API calls (10 per request) | ~2,000   | ~2,000    | ~2 minutes |

**Total: ~2 minutes instead of ~17 hours.** This is a **99.8% reduction** in LLM calls.

**Why each stage:**

- **SQL** handles numeric comparisons blazingly fast using indexes
- **Rule Engine** handles array operations (employment type matching) that are messy in SQL
- **LLM** adds qualitative assessment and generates human-readable match reasons

### 4. Idempotent Operations

- CSV upload uses `ON CONFLICT ... DO UPDATE` — re-uploading is safe
- Match creation uses `UNIQUE(user_id, product_id)` — no duplicate matches
- Notifications track `notified = TRUE/FALSE` — no duplicate emails

## 📁 Project Structure

```
ClickPe/
├── docker-compose.yml              # n8n + PostgreSQL containers
├── serverless.yml                  # AWS Lambda, S3, IAM configuration
├── frontend/
│   └── index.html                  # CSV upload UI (presigned URL flow)
├── lambda/
│   ├── csv_processor/
│   │   ├── handler.py              # S3 event → parse CSV → Postgres → webhook
│   │   └── requirements.txt        # Python dependencies (psycopg2)
│   └── presigned_url/
│       └── handler.py              # Generate S3 presigned URL for direct upload
├── n8n-workflows/
│   ├── workflow_a_crawler.json     # Scheduled crawler for loan products
│   ├── workflow_b_matching.json    # 3-stage optimized matching engine
│   └── workflow_c_notification.json # Email notifications via AWS SES
├── db/
│   └── schema.sql                  # PostgreSQL schema (auto-runs on first start)
├── users.csv                       # Sample data (10,000 users)
└── README.md                       # This file
```

## 🎥 Demo Video

[Link to demo video]

The demo covers:

1. Walking through each n8n workflow and explaining the logic of every node
2. Starting the pipeline by uploading the CSV
3. Showing the n8n execution logs for all three workflows
4. Showing a received email in a test inbox

## 🛠️ Technologies Used

| Component        | Technology                    |
| ---------------- | ----------------------------- |
| Backend          | Python 3.11                   |
| Cloud            | AWS (Lambda, S3, SES)         |
| Database         | PostgreSQL 16                 |
| Workflow Engine  | n8n (self-hosted via Docker)  |
| Infrastructure   | Serverless Framework          |
| Containerization | Docker Compose                |
| LLM              | Google Gemini API (free tier) |
| Frontend         | Static HTML/CSS/JavaScript    |
