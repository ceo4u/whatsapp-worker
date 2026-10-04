# Deploy to Hostinger

## 1. Push to GitHub

```bash
cd whatsapp-worker-standalone
git init
git add .
git commit -m "Initial worker"
git remote add origin https://github.com/ceo4u/whatsapp-worker.git
git push -u origin main
```

## 2. Hostinger cPanel Setup

### 2.1 Create Python Application

1. Login to Hostinger cPanel
2. Software → Setup Python App
3. Click "Create Application"
4. Fill:
   - **Python version:** 3.11
   - **Application root:** whatsapp-worker
   - **Application URL:** worker.yourdomain.com
   - **Application startup file:** passenger_wsgi.py
   - **Application Entry point:** application
5. Click Create

### 2.2 SSH into Server

```bash
ssh username@yourdomain.com -p 65002
```

### 2.3 Clone Repository

```bash
cd ~
rm -rf whatsapp-worker
git clone https://github.com/ceo4u/whatsapp-worker.git whatsapp-worker
cd whatsapp-worker
```

### 2.4 Install Dependencies

```bash
source /home/USERNAME/virtualenv/whatsapp-worker/3.11/bin/activate
pip install -r requirements.txt
```

### 2.5 Create .env

```bash
nano .env
```

Paste:
```
DATABASE_URL=postgresql://...
GEMINI_API_KEY=...
```

Save: Ctrl+X → Y → Enter

### 2.6 Restart Python App

cPanel → Setup Python App → Restart

### 2.7 Test

```bash
curl https://worker.yourdomain.com/
# Expected: {"status":"ok","service":"crawler-worker-neon"}
```

## 3. Setup Cron Job

cPanel → Advanced → Cron Jobs

Add New Cron Job:
- **Minute:** *
- **Hour:** *
- **Day:** *
- **Month:** *
- **Weekday:** *
- **Command:** curl -s -X POST https://worker.yourdomain.com/worker/tick > /dev/null 2>&1

## 4. Update Frontend

In Vercel environment variables:
```
WORKER_URL=https://worker.yourdomain.com
```
