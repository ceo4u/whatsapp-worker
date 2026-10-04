# WhatsApp AI Worker (Hostinger Deploy)

FastAPI worker for crawling websites and training bots.

## Deploy on Hostinger

1. Push this folder to a GitHub repo
2. In Hostinger cPanel → Setup Python App
3. Fill the form:
   - Python version: 3.11
   - Application root: whatsapp-worker
   - Application URL: worker.yourdomain.com
   - Application startup file: passenger_wsgi.py
   - Application Entry point: application
4. SSH into Hostinger and:
   ```bash
   cd ~/whatsapp-worker
   git clone https://github.com/ceo4u/whatsapp-worker.git .
   source /home/USERNAME/virtualenv/whatsapp-worker/3.11/bin/activate
   pip install -r requirements.txt
   ```
5. Restart the Python app from cPanel
6. Test: `curl https://worker.yourdomain.com/`

## Environment Variables

Create `.env` file in the application root with:
- `DATABASE_URL`
- `GEMINI_API_KEY`

## Cron Job

Set up in cPanel → Cron Jobs:
- Schedule: `* * * * *` (every minute)
- Command: `curl -s -X POST https://worker.yourdomain.com/worker/tick`

## Endpoints

- `GET /`  → health check
- `POST /ingest`  → queue crawl job
- `POST /train-text`  → queue training job
- `POST /worker/tick`  → process 1 pending job (cron)
