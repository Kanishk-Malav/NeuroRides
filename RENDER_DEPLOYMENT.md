# Render Deployment Guide for NeuroRides

## 🚨 Current Issue: Worker Timeout

Your deployment is experiencing worker timeouts due to memory constraints. This guide will fix it.

## Quick Fix

### 1. Update Render Service Settings

Go to your Render dashboard and update these settings:

**Build Command:**
```bash
./build.sh
```

**Start Command:**
```bash
gunicorn neurorides.wsgi:application --config gunicorn.conf.py
```

### 2. Environment Variables

Add these in Render dashboard:

```
DEBUG=False
SECRET_KEY=<generate-a-strong-secret-key>
ALLOWED_HOSTS=neurorides.onrender.com
DATABASE_URL=<your-database-url>
REDIS_URL=<your-redis-url-or-leave-default>
PYTHON_VERSION=3.11.0
WEB_CONCURRENCY=1
PYTHONUNBUFFERED=1
```

### 3. Upgrade Plan (Recommended)

The free tier has only 512MB RAM which causes the timeouts. Upgrade to:
- **Starter Plan ($7/month)**: 512MB RAM, better for production
- **Standard Plan ($25/month)**: 2GB RAM, recommended for production

## Files Created for Render

1. **render.yaml** - Render service configuration
2. **gunicorn.conf.py** - Optimized Gunicorn config (1 worker, 120s timeout)
3. **Procfile** - Process definitions
4. **build.sh** - Build script
5. **runtime.txt** - Python version specification

## Why Workers Are Timing Out

1. **Memory Constraints**: Free tier has only 512MB RAM
2. **Heavy Imports**: Django + Celery + all apps load at startup
3. **Multiple Workers**: Default 4 workers × 512MB = too much memory
4. **Slow Startup**: Cold starts take >30 seconds

## Optimizations Applied

### 1. Reduced Workers
```python
# gunicorn.conf.py
workers = 1  # Down from 4
timeout = 120  # Up from 30
```

### 2. Lazy Celery Loading
```python
# settings.py
try:
    from dispatch.celery_config import ...
except ImportError:
    CELERY_TASK_ROUTES = {}
```

### 3. Disabled Preloading
```python
# gunicorn.conf.py
preload_app = False  # Reduces memory usage
```

## Deployment Steps

### Option A: Using Render Dashboard

1. Go to https://dashboard.render.com
2. Select your service "neurorides"
3. Go to Settings
4. Update **Build Command**: `./build.sh`
5. Update **Start Command**: `gunicorn neurorides.wsgi:application --config gunicorn.conf.py`
6. Add environment variables (see above)
7. Click "Manual Deploy" → "Deploy latest commit"

### Option B: Using render.yaml

1. Commit the new files:
```bash
git add render.yaml gunicorn.conf.py Procfile build.sh runtime.txt
git commit -m "Fix worker timeout with optimized config"
git push
```

2. Render will auto-deploy with new configuration

## Testing Deployment

### 1. Check Logs
```bash
# In Render dashboard, go to Logs tab
# Look for:
✓ "Gunicorn server is ready"
✓ "Worker spawned"
✓ No "WORKER TIMEOUT" errors
```

### 2. Test Endpoints
```bash
# Health check
curl https://neurorides.onrender.com/admin/

# Should return 200 or redirect to login
```

### 3. Monitor Memory
```bash
# In Render dashboard, go to Metrics tab
# Memory usage should be < 400MB
```

## Troubleshooting

### Still Getting Timeouts?

1. **Increase Timeout**:
```python
# gunicorn.conf.py
timeout = 180  # Increase to 3 minutes
```

2. **Disable Celery Temporarily**:
```python
# settings.py
CELERY_TASK_ALWAYS_EAGER = True  # Run tasks synchronously
```

3. **Upgrade Plan**: Free tier is really limited

### Workers Keep Dying?

1. **Check Memory Usage**: Upgrade if consistently >90%
2. **Reduce Imports**: Comment out unused apps in INSTALLED_APPS
3. **Use External Services**: Move Celery to separate worker service

### Slow Response Times?

1. **Enable Caching**:
```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

2. **Add Database Indexes**: Already done in models
3. **Use CDN**: For static files

## Production Recommendations

### 1. Database
- Use Render PostgreSQL (not SQLite)
- Enable connection pooling
- Set up automated backups

### 2. Redis
- Use Render Redis or Upstash
- Required for Celery and caching
- Free tier available

### 3. Static Files
- Use WhiteNoise (already configured)
- Or use S3/CloudFront for better performance

### 4. Monitoring
- Enable Render metrics
- Set up Sentry for error tracking
- Configure uptime monitoring

### 5. Security
- Set DEBUG=False (already done)
- Use strong SECRET_KEY
- Enable HTTPS (automatic on Render)
- Set proper ALLOWED_HOSTS

## Environment Variables Reference

### Required
```
SECRET_KEY=<generate-strong-key>
DEBUG=False
ALLOWED_HOSTS=neurorides.onrender.com
```

### Database
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Redis (Optional but recommended)
```
REDIS_URL=redis://host:6379/0
```

### Payment Gateways
```
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
```

### Email
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## Cost Optimization

### Free Tier
- 1 web service (512MB RAM)
- 1 PostgreSQL database (256MB)
- 1 Redis instance (25MB)
- **Total: $0/month**
- **Limitation**: Workers timeout, slow cold starts

### Starter Tier ($7/month)
- 1 web service (512MB RAM, no sleep)
- Better performance
- No cold starts
- **Recommended for MVP**

### Production Tier ($32/month)
- 1 web service (2GB RAM)
- 1 PostgreSQL (1GB)
- 1 Redis (256MB)
- **Recommended for production**

## Next Steps

1. ✅ Apply the configuration changes above
2. ✅ Redeploy the service
3. ✅ Monitor logs for successful startup
4. ✅ Test all endpoints
5. ⚠️ Consider upgrading plan if timeouts persist
6. ⚠️ Set up PostgreSQL database
7. ⚠️ Set up Redis for Celery
8. ⚠️ Configure payment gateways
9. ⚠️ Set up monitoring and alerts

## Support

If issues persist:
1. Check Render status page
2. Review application logs
3. Check memory/CPU metrics
4. Contact Render support
5. Consider upgrading plan

---

**Status**: Configuration optimized for Render free tier
**Last Updated**: December 4, 2024
