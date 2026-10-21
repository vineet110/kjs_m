# System & Development Prerequisites — KJS Digital Platform (`kjs_m`)

This document outlines everything needed on your machine or cloud server to run, develop, and test the **KJS India Digital Platform**.

---

## 1. System Runtime Requirements

| Dependency | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | `3.11.x` | `3.12.x` | Required for the FastAPI backend, APScheduler, and background worker. |
| **Node.js** | `18.17.x` | `20.x` LTS | Required to build and run the Next.js App Router frontend. |
| **npm** or **pnpm**| `9.x`+ (npm) / `8.x`+ (pnpm)| Latest | Package manager for frontend dependencies. |
| **Docker Engine** | `24.0.x`+ | Latest | Required to run PostgreSQL 16 (with pgvector) and Apache Superset. |
| **Docker Compose**| `v2.20.x`+ | Latest | Bundles all multi-container services in `docker-compose.yml`. |

---

## 2. Infrastructure & Database Dependencies

### PostgreSQL 16 with `pgvector`
The database requires the `vector` extension for storing 384-dimensional vector embeddings for the **Koko AI assistant**.
- If running via Docker: The provided `docker-compose.yml` uses the official `pgvector/pgvector:pg16` image automatically.
- If using a standalone PostgreSQL instance:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE SCHEMA IF NOT EXISTS analytics;
  ```

### Apache Superset (Insights & Analytics)
- Self-hosted container using `apache/superset:3.1.0`.
- Requires `psycopg2-binary` to connect to PostgreSQL.
- Embedded inside the Next.js admin console using guest JWT tokens.

---

## 3. External API Credentials & Services

To enable full production functionality, configure the following keys in your `.env` file:

### 1. Anthropic Claude API (Koko AI Assistant)
- **Used For:** Streaming responses, knowledge base Q&A, and lead capture summaries.
- **Model:** Claude Haiku-class model.
- **Config:** `ANTHROPIC_API_KEY=sk-ant-api...`
- **Recommended Cap:** $20–$50/month.

### 2. Meta WhatsApp Business Cloud API
- **Used For:** Order board deadline threshold alerts (50%, 85%, 100%) to employees.
- **Prerequisites:** Meta Business Account verification & 3 pre-approved message templates.
- **Config:**
  - `WHATSAPP_API_TOKEN`
  - `WHATSAPP_PHONE_NUMBER_ID`
  - `WHATSAPP_BUSINESS_ACCOUNT_ID`

### 3. Transactional Email (Resend or Brevo)
- **Used For:** Order board deadline emails, document delete approvals, password resets, and visitor enquiries.
- **Config:**
  - `RESEND_API_KEY`
  - `ALERT_FROM_EMAIL=alerts@kjsindia.com`

### 4. Cloudflare Tunnel (Staging & Production)
- **Used For:** Secure public HTTPS routing without opening firewall ports.

---

## 4. How to Run the Project

### Option A: Using Docker Compose (Recommended)
This starts all services (PostgreSQL with pgvector, FastAPI, Next.js, Worker, and Superset) in one command:
```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Build and launch all containers
docker compose up -d --build

# 3. Apply database migrations
docker compose exec backend alembic upgrade head
```

- **Frontend (Next.js):** [http://localhost:3000](http://localhost:3000)
- **Backend API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Superset Analytics:** [http://localhost:8088](http://localhost:8088)

---

### Option B: Local Development (Without Docker)

#### 1. Backend Setup:
```bash
cd backend
python -m venv .venv

# Windows activation:
.venv\Scripts\activate
# macOS/Linux activation:
# source .venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```
Navigate to [http://localhost:3000](http://localhost:3000) in your browser.
