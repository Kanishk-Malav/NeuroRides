# 🚀 Deployment Checklist - Fix Worker Timeout

## ⚠️ URGENT: Your Render deployment is experiencing worker timeouts!

Follow these steps to fix it immediately:

## Step 1: Update Render Configuration (5 minutes)

### Go to Render Dashboard
1. Visit https://dashboard.render.com
2. Select your "neurorides" service
3. Click "Settings"

### Update Build Command
```bash
./build.sh
```

### Update Start Command
```bash
gunicorn neurorides.wsgi:application --config gunicorn.conf.py
```

### Add/Update Environment Variables
```
DEBUG=False
SECRET_KEY=your-super-secret-key-change-this-in-production
ALLOWED_HOSTS=neurorides.onrender.com
PYTHON_VERSION=3.11.0
WEB_CONCURRENCY=1
PYTHONUNBUFFERED=1
```

## Step 2: Commit and Push New Files

```bash
git add render.yaml gunicorn.conf.py Procfile build.sh runtime.txt
git add neurorides/health.py neurorides/health_urls.py
git add RENDER_DEPLOYMENT.md DEPLOYMENT_CHECKLIST.md
git commit -m "Fix worker timeout with optimized Render configuration"
git push origin main
```

## Step 3: Manual Deploy

1. In Render dashboard, click "Manual Deploy"
2. Select "Deploy latest commit"
3. Wait for deployment (should take 2-3 minutes)

## Step 4: Verify Deployment

### Check Logs
Look for these success indicators:
```
✓ Starting Gunicorn server...
✓ Gunicorn server is ready. Spawning workers...
✓ Worker spawned (pid: XX)
✓ Listening at: http://0.0.0.0:10000
```

### Test Health Endpoint
```bash
curl https://neurorides.onrender.com/health/
# Should return: {"status":"healthy","service":"neurorides","version":"1.0.0"}
```

### Test Admin
```bash
curl https://neurorides.onrender.com/admin/
# Should return 200 or redirect to login
```

## What Was Fixed

### 1. Reduced Workers
- **Before**: 4 workers (too much memory)
- **After**: 1 worker (optimized for free tier)

### 2. Increased Timeout
- **Before**: 30 seconds (too short for cold start)
- **After**: 120 seconds (enough time to start)

### 3. Optimized Imports
- **Before**: All Celery configs loaded at startup
- **After**: Lazy loading with try/except

### 4. Added Health Checks
- `/health/` - Basic health check
- `/health/detailed/` - With database check
- `/health/ready/` - Readiness probe
- `/health/live/` - Liveness probe

## Files Created

- ✅ `render.yaml` - Render service configuration
- ✅ `gunicorn.conf.py` - Optimized Gunicorn settings
- ✅ `Procfile` - Process definitions
- ✅ `build.sh` - Build script
- ✅ `runtime.txt` - Python version
- ✅ `neurorides/health.py` - Health check views
- ✅ `neurorides/health_urls.py` - Health check URLs
- ✅ `RENDER_DEPLOYMENT.md` - Detailed deployment guide
- ✅ `DEPLOYMENT_CHECKLIST.md` - This file

## Expected Results

### Before Fix
```
[CRITICAL] WORKER TIMEOUT (pid:XX)
[ERROR] Worker (pid:XX) was sent SIGKILL! Perhaps out of memory?
```

### After Fix
```
[INFO] Starting Gunicorn server...
[INFO] Gunicorn server is ready. Spawning workers...
[INFO] Worker spawned (pid: XX)
[INFO] Listening at: http://0.0.0.0:10000
```

## If Still Having Issues

### Option 1: Increase Timeout Further
Edit `gunicorn.conf.py`:
```python
timeout = 180  # Increase to 3 minutes
```

### Option 2: Disable Celery Temporarily
Edit `neurorides/settings.py`:
```python
CELERY_TASK_ALWAYS_EAGER = True
```

### Option 3: Upgrade Render Plan
- Free tier: 512MB RAM (causes timeouts)
- Starter: $7/month, 512MB RAM, no sleep
- Standard: $25/month, 2GB RAM (recommended)

## Monitoring

### Check Memory Usage
1. Go to Render dashboard
2. Click "Metrics" tab
3. Monitor memory usage
4. Should be < 400MB on free tier

### Check Response Times
```bash
curl -w "@-" -o /dev/null -s https://neurorides.onrender.com/health/ <<'EOF'
    time_namelookup:  %{time_namelookup}\n
       time_connect:  %{time_connect}\n
    time_appconnect:  %{time_appconnect}\n
      time_redirect:  %{time_redirect}\n
   time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
         time_total:  %{time_total}\n
EOF
```

## Next Steps After Fix

1. ✅ Verify deployment is working
2. ⚠️ Set up PostgreSQL database (currently using SQLite)
3. ⚠️ Set up Redis for Celery
4. ⚠️ Configure payment gateways
5. ⚠️ Set up monitoring (Sentry, etc.)
6. ⚠️ Configure custom domain
7. ⚠️ Set up SSL certificate (automatic on Render)
8. ⚠️ Configure email service
9. ⚠️ Set up automated backups
10. ⚠️ Create staging environment

## Support

- **Render Docs**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Django Docs**: https://docs.djangoproject.com
- **Gunicorn Docs**: https://docs.gunicorn.org

## Quick Commands

```bash
# Check if service is up
curl https://neurorides.onrender.com/health/

# Check detailed health
curl https://neurorides.onrender.com/health/detailed/

# View logs (in Render dashboard)
# Settings → Logs

# Manual deploy (in Render dashboard)
# Manual Deploy → Deploy latest commit

# Restart service (in Render dashboard)
# Settings → Restart Service
```

---

**Status**: Ready to deploy
**Priority**: URGENT - Fix worker timeouts
**Estimated Time**: 5-10 minutes
**Last Updated**: December 4, 2024
