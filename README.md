# WhatsApp AI Worker

FastAPI worker for crawling websites, generating embeddings, and 
training WhatsApp AI bots.

## Overview

This worker:
- Crawls websites via sitemap and internal links
- Extracts clean text content
- Chunks text intelligently
- Generates 768-dim embeddings via Gemini
- Stores vectors in Neon PostgreSQL (pgvector)
- Processes training text from business owners
- Runs via Hostinger cPanel Python App + cron

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health check |
| POST | `/ingest` | Queue website crawl job |
| POST | `/train-text` | Queue text training job |
| GET/POST | `/worker/tick` | Process 1 pending job (cron) |

## Deployment on Hostinger

### Prerequisites
- Hostinger shared hosting with Python support
- SSH access enabled
- Neon PostgreSQL database
- Gemini API key

### Steps

1. **Create Python App in cPanel**
   - Python version: 3.11
   - Application root: `whatsapp-worker`
   - Application URL: `worker.yourdomain.com`
   - Application startup file: `passenger_wsgi.py`
   - Application Entry point: `application`

2. **SSH into server**
   ```bash
   ssh username@yourdomain.com -p 65002
   ```

3. **Clone this repo**
   ```bash
   cd ~
   rm -rf whatsapp-worker
   git clone https://github.com/ceo4u/whatsapp-worker.git whatsapp-worker
   cd whatsapp-worker
   ```

4. **Activate virtualenv**
   ```bash
   source /home/USERNAME/virtualenv/whatsapp-worker/3.11/bin/activate
   ```

5. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

6. **Create .env file**
   ```bash
   nano .env
   ```
   Paste:
   ```text
   DATABASE_URL=postgresql://...
   GEMINI_API_KEY=...
   ```
   Save: `Ctrl+X` → `Y` → `Enter`

7. **Set permissions**
   ```bash
   chmod 600 .env
   mkdir -p tmp
   touch tmp/restart.txt
   ```

8. **Restart app**
   cPanel → Setup Python App → Restart

9. **Test**
   ```bash
   curl https://worker.yourdomain.com/
   # Expected: {"status":"ok","service":"crawler-worker-neon"}
   ```

## Cron Job
Setup in cPanel → Cron Jobs → Add New Cron Job:
- **Schedule:** `* * * * *` (every minute)
- **Command:** `curl -s -X POST https://worker.yourdomain.com/worker/tick > /dev/null 2>&1`

This processes one pending crawl/training job per minute.

## Environment Variables
| Variable | Description | Required |
|----------|-------------|----------|
| DATABASE_URL | Neon PostgreSQL connection string | Yes |
| GEMINI_API_KEY | Google Gemini API key for embeddings | Yes |

## License
Proprietary
