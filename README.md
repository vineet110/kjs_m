# KJS India Digital Platform (`kjs_m`)

A comprehensive digital enterprise platform designed for **KJS India** featuring:
- **Public Website with Koko AI**: Product showcase, dynamic moving offers ticker, category unlock gate (DPDP Act 2023 compliant), and Claude Haiku-powered RAG assistant with pgvector.
- **Employee Portal**: Server-time punch attendance (Mon–Sat working calendar, night shift support, auto-closing & regularization), availability toggle, task kanban with query outcome logging, and member-scoped order board step tracking.
- **Admin Console**: Automatic task assignment engine (least-busy-first/round-robin with dry-run preview), 5-checkpoint order board manager (`ABC117-xxxx`), file upload versioning with delete approval workflow, append-only immutable audit logging, team attendance grid with payroll export, and embedded Apache Superset analytics.

---

## Tech Stack
- **Frontend**: Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui, next-intl (English & Hindi)
- **Backend API**: FastAPI (Python 3.12), SQLAlchemy 2.0 (Async), Alembic, Pydantic v2, APScheduler
- **Database**: PostgreSQL 16 + pgvector (embedding vector(384) for Koko)
- **Queue/Worker**: PostgreSQL job queue (`FOR UPDATE SKIP LOCKED`)
- **Analytics**: Apache Superset (Dockerized, embedded via Guest Token SDK)
- **External Services**: Meta WhatsApp Business Cloud API, Resend/Brevo (Email), Anthropic Claude Haiku API

---

## Quick Start

### 1. Configure Environment
```bash
cp .env.example .env
```

### 2. Start Services via Docker Compose
```bash
docker compose up -d --build
```
- **Next.js Web Application**: http://localhost:3000
- **FastAPI Documentation**: http://localhost:8000/docs
- **Apache Superset**: http://localhost:8088

### 3. Database Migrations
```bash
docker compose exec backend alembic upgrade head
```
