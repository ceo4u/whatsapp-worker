# Deployment Guide

## 1. Push to GitHub
From `whatsapp-worker-standalone/` folder:

```bash
git init
git add .
git commit -m "Initial worker setup"
git branch -M main
git remote add origin https://github.com/ceo4u/whatsapp-worker.git
git push -u origin main
```

## 2. Hostinger Setup

### 2.1 Create Python App
1. Login to Hostinger hPanel
2. Go to **Setup Python App**
3. Click **Create Application**
4. Fill form:
   - **Python version:** 3.11
   - **Application root:** `whatsapp-worker`
   - **Application URL:** `worker.yourdomain.com` (create subdomain first)
   - **Application startup file:** `passenger_wsgi.py`
   - **Application Entry point:** `application`
5. Click **Create**

### 2.2 SSH Access
Get SSH credentials from:
- hPanel → Advanced → SSH Access
- Username, host, port (usually 65002)
- Password or SSH key

### 2.3 Deploy Code
```bash
ssh USERNAME@yourdomain.com -p 65002

cd ~
rm -rf whatsapp-worker
git clone https://github.com/ceo4u/whatsapp-worker.git whatsapp-worker
cd whatsapp-worker

source /home/USERNAME/virtualenv/whatsapp-worker/3.11/bin/activate
pip install -r requirements.txt
```

### 2.4 Configure .env
```bash
nano .env
```
Paste credentials, save.

### 2.5 Set Permissions
```bash
chmod 600 .env
mkdir -p tmp
touch tmp/restart.txt
```

### 2.6 Restart
hPanel → Setup Python App → Restart
Or SSH:
```bash
touch ~/whatsapp-worker/tmp/restart.txt
```

### 2.7 Test
```bash
curl https://worker.yourdomain.com/
# Expected: {"status":"ok","service":"crawler-worker-neon"}
```

## 3. Setup Cron Job
hPanel → Cron Jobs → Add New Cron Job:
- **Minute:** `*`
- **Hour:** `*`
- **Day:** `*`
- **Month:** `*`
- **Weekday:** `*`
- **Command:** `curl -s -X POST https://worker.yourdomain.com/worker/tick > /dev/null 2>&1`

## 4. Update Frontend
In Vercel environment variables:
```text
WORKER_URL=https://worker.yourdomain.com
```

## 5. Verify End-to-End
1. Trigger crawl from Next.js: `POST /api/companies`
2. Check `crawl_jobs` table in Neon: status should be `pending`
3. Wait 1 minute — cron runs
4. Check status: `done` or `processing`
5. Check `company_docs` table for new chunks

## Troubleshooting

### 500 Internal Server Error
```bash
tail -50 ~/whatsapp-worker/stderr.log
```
If `"No module named 'a2wsgi'"`:
```bash
source /home/USERNAME/virtualenv/whatsapp-worker/3.11/bin/activate
pip install a2wsgi
```

### Database connection failed
- Check `.env` file exists
- Verify `DATABASE_URL` format
- Test: `psql "$DATABASE_URL" -c "SELECT 1"`

### Cron not running
- Check hPanel → Cron Jobs → Logs
- Test command manually: `curl https://worker.yourdomain.com/worker/tick`

## Logs
| Log | Location |
|-----|----------|
| App errors | `~/whatsapp-worker/stderr.log` |
| App stdout | `~/whatsapp-worker/stdout.log` |
| Passenger | `~/whatsapp-worker/passenger.log` |
