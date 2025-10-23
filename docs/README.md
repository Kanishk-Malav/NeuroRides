# NeuroRides Platform Documentation

## Overview

NeuroRides is a comprehensive ride-sharing platform built with Django and React, featuring real-time tracking, intelligent dispatch, secure payments, and advanced analytics.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [API Documentation](#api-documentation)
6. [User Guides](#user-guides)
7. [Development](#development)
8. [Deployment](#deployment)
9. [Monitoring](#monitoring)
10. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL with PostGIS extension
- Redis

### Development Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd neurorides-platform
```

2. Copy environment configuration:
```bash
cp .env.example .env
```

3. Start services with Docker Compose:
```bash
docker-compose up -d
```

4. Run database migrations:
```bash
docker-compose exec web python manage.py migrate
```

5. Create initial data:
```bash
docker-compose exec web python manage.py create_initial_users
docker-compose exec web python manage.py create_sample_fleet
```

6. Access the application:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Admin Panel: http://localhost:8000/admin

## Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React Frontend │    │  Django Backend │    │   PostgreSQL    │
│   (Port 3000)   │◄──►│   (Port 8000)   │◄──►│   (Port 5432)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│      Redis      │◄──►│  Celery Workers │    │      Nginx      │
│   (Port 6379)   │    │  (Background)   │    │   (Port 80)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Features

- **Real-time Communication**: WebSocket connections for live tracking
- **Intelligent Dispatch**: PostGIS-based vehicle assignment algorithms
- **Secure Payments**: PCI-compliant payment processing with encryption
- **Advanced Analytics**: Real-time KPIs and comprehensive reporting
- **Fleet Management**: Vehicle tracking, maintenance scheduling, telemetry
- **Role-based Access**: Rider, Operator, and Admin user roles

## Installation

### Local Development

#### Backend Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up database:
```bash
createdb neurorides
psql neurorides -c "CREATE EXTENSION postgis;"
```

4. Configure environment variables:
```bash
export DATABASE_URL="postgresql://user:password@localhost/neurorides"
export REDIS_URL="redis://localhost:6379"
export SECRET_KEY="your-secret-key"
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Start development server:
```bash
python manage.py runserver
```

#### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm start
```

### Production Deployment

See [Deployment Guide](deployment.md) for detailed production setup instructions.

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | - | Yes |
| `REDIS_URL` | Redis connection string | - | Yes |
| `SECRET_KEY` | Django secret key | - | Yes |
| `DEBUG` | Enable debug mode | False | No |
| `ALLOWED_HOSTS` | Comma-separated allowed hosts | localhost | No |
| `STRIPE_PUBLIC_KEY` | Stripe public key | - | Yes |
| `STRIPE_SECRET_KEY` | Stripe secret key | - | Yes |
| `RAZORPAY_KEY_ID` | Razorpay key ID | - | Yes |
| `RAZORPAY_KEY_SECRET` | Razorpay secret key | - | Yes |
| `EMAIL_HOST` | SMTP host for emails | - | No |
| `EMAIL_PORT` | SMTP port | 587 | No |
| `EMAIL_HOST_USER` | SMTP username | - | No |
| `EMAIL_HOST_PASSWORD` | SMTP password | - | No |

### Database Configuration

The platform uses PostgreSQL with PostGIS extension for spatial data operations:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'neurorides',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Redis Configuration

Redis is used for caching, session storage, and Celery message broker:

```python
REDIS_URL = 'redis://localhost:6379'
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

## API Documentation

### Authentication

The API uses JWT (JSON Web Tokens) for authentication. Include the token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Base URL

- Development: `http://localhost:8000/api/`
- Production: `https://your-domain.com/api/`

### Core Endpoints

#### Authentication
- `POST /api/accounts/register/` - User registration
- `POST /api/accounts/login/` - User login
- `POST /api/accounts/logout/` - User logout
- `GET /api/accounts/profile/` - Get user profile
- `PATCH /api/accounts/profile/` - Update user profile

#### Rides
- `GET /api/rides/` - List user rides
- `POST /api/rides/` - Create new ride
- `GET /api/rides/{id}/` - Get ride details
- `POST /api/rides/{id}/cancel/` - Cancel ride
- `POST /api/rides/estimate-fare/` - Estimate ride fare

#### Fleet Management (Operators only)
- `GET /api/fleet/vehicles/` - List vehicles
- `POST /api/fleet/vehicles/` - Add new vehicle
- `GET /api/fleet/vehicles/{id}/` - Get vehicle details
- `PATCH /api/fleet/vehicles/{id}/` - Update vehicle
- `POST /api/fleet/vehicles/{id}/telemetry/` - Submit telemetry data

#### Payments
- `GET /api/payments/` - List payments
- `POST /api/payments/` - Process payment
- `GET /api/payments/{id}/` - Get payment details
- `POST /api/payments/{id}/refund/` - Process refund

#### Analytics (Admin/Operator only)
- `GET /api/analytics/dashboard/` - Dashboard data
- `GET /api/analytics/reports/` - List reports
- `POST /api/analytics/reports/` - Generate report

### Response Format

All API responses follow this format:

```json
{
  "success": true,
  "data": {
    // Response data
  },
  "message": "Success message",
  "errors": null
}
```

Error responses:

```json
{
  "success": false,
  "data": null,
  "message": "Error message",
  "errors": {
    "field": ["Error details"]
  }
}
```

### Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error

## User Guides

### For Riders

#### Booking a Ride

1. **Login/Register**: Create an account or login to existing account
2. **Set Pickup Location**: Use the map or enter address manually
3. **Set Destination**: Choose your destination on the map
4. **Select Ride Type**: Choose from available vehicle types
5. **Review Fare**: Check estimated fare and confirm booking
6. **Track Ride**: Monitor vehicle location and estimated arrival
7. **Complete Payment**: Pay securely after ride completion

#### Managing Your Account

- **Profile**: Update personal information and preferences
- **Payment Methods**: Add/remove credit cards and payment methods
- **Ride History**: View past rides and receipts
- **Support**: Contact customer support for issues

### For Operators

#### Fleet Management

1. **Vehicle Overview**: Monitor all vehicles in real-time
2. **Add Vehicles**: Register new vehicles in the system
3. **Vehicle Status**: Update vehicle availability and status
4. **Maintenance**: Schedule and track vehicle maintenance
5. **Telemetry**: Monitor vehicle health and performance data

#### Dispatch Operations

1. **Ride Requests**: View incoming ride requests
2. **Vehicle Assignment**: Assign vehicles to rides manually if needed
3. **Route Optimization**: Monitor dispatch efficiency
4. **Performance Metrics**: Track operator KPIs

### For Administrators

#### System Management

1. **User Management**: Manage rider and operator accounts
2. **Fleet Configuration**: Configure vehicle types and pricing
3. **Analytics Dashboard**: Monitor system-wide metrics
4. **Report Generation**: Create custom reports
5. **System Settings**: Configure platform parameters

#### Financial Management

1. **Revenue Tracking**: Monitor daily/monthly revenue
2. **Payment Processing**: Handle payment issues and refunds
3. **Commission Management**: Track operator commissions
4. **Financial Reports**: Generate financial statements

## Development

### Project Structure

```
neurorides-platform/
├── accounts/           # User authentication and management
├── analytics/          # Analytics and reporting
├── dispatch/           # Intelligent dispatch system
├── fleet/             # Fleet management
├── payments/          # Payment processing
├── realtime/          # WebSocket and real-time features
├── rides/             # Ride booking and management
├── frontend/          # React frontend application
├── docker/            # Docker configuration files
├── scripts/           # Deployment and utility scripts
├── docs/              # Documentation
├── requirements.txt   # Python dependencies
├── docker-compose.yml # Docker Compose configuration
└── manage.py          # Django management script
```

### Development Workflow

1. **Feature Development**:
   - Create feature branch from main
   - Implement backend changes with tests
   - Update frontend components if needed
   - Write/update documentation
   - Submit pull request

2. **Testing**:
   ```bash
   # Run backend tests
   python manage.py test
   
   # Run frontend tests
   cd frontend && npm test
   
   # Run integration tests
   python manage.py test tests.test_integration
   ```

3. **Code Quality**:
   ```bash
   # Python linting
   flake8 .
   black .
   
   # JavaScript linting
   cd frontend && npm run lint
   ```

### Adding New Features

#### Backend (Django)

1. Create new app if needed:
```bash
python manage.py startapp myapp
```

2. Define models in `models.py`
3. Create serializers in `serializers.py`
4. Implement views in `views.py`
5. Add URL patterns in `urls.py`
6. Write tests in `tests.py`

#### Frontend (React)

1. Create components in `frontend/src/components/`
2. Add Redux slices in `frontend/src/store/slices/`
3. Update routing in `frontend/src/App.tsx`
4. Add TypeScript types in `frontend/src/types/`
5. Write component tests

### Database Migrations

```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

### Background Tasks

The platform uses Celery for background task processing:

```bash
# Start Celery worker
celery -A neurorides worker -l info

# Start Celery beat (scheduler)
celery -A neurorides beat -l info

# Monitor tasks
celery -A neurorides flower
```

## Deployment

### Production Requirements

- **Server**: Ubuntu 20.04+ or similar Linux distribution
- **Memory**: Minimum 4GB RAM (8GB+ recommended)
- **Storage**: 50GB+ SSD storage
- **Network**: Stable internet connection with public IP
- **SSL Certificate**: For HTTPS (Let's Encrypt recommended)

### Deployment Steps

1. **Server Setup**:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **Application Deployment**:
```bash
# Clone repository
git clone <repository-url> /opt/neurorides
cd /opt/neurorides

# Configure environment
cp .env.example .env.production
# Edit .env.production with production values

# Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d
```

3. **SSL Setup**:
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com
```

### Environment-Specific Configurations

#### Development
- Debug mode enabled
- SQLite database (optional)
- Local file storage
- Detailed error messages

#### Staging
- Debug mode disabled
- PostgreSQL database
- Cloud storage (optional)
- Error logging enabled

#### Production
- Debug mode disabled
- PostgreSQL with connection pooling
- Cloud storage (S3/GCS)
- Comprehensive monitoring
- SSL/TLS encryption
- Rate limiting enabled

## Monitoring

### Health Checks

The platform provides several health check endpoints:

- `/health/` - Basic health status
- `/health/detailed/` - Detailed service status
- `/metrics/` - Prometheus-compatible metrics

### Logging

Logs are structured in JSON format and include:

- Request/response logging
- Error tracking
- Performance metrics
- Security events
- Business events (rides, payments)

### Monitoring Stack

Recommended monitoring tools:

1. **Application Monitoring**: Sentry for error tracking
2. **Infrastructure Monitoring**: Prometheus + Grafana
3. **Log Management**: ELK Stack (Elasticsearch, Logstash, Kibana)
4. **Uptime Monitoring**: Pingdom or similar service

### Key Metrics to Monitor

#### System Metrics
- CPU and memory usage
- Database connection pool
- Redis memory usage
- Response times
- Error rates

#### Business Metrics
- Active rides
- Revenue per hour
- Vehicle utilization
- Customer satisfaction
- Payment success rate

## Troubleshooting

### Common Issues

#### Database Connection Issues

**Problem**: `django.db.utils.OperationalError: could not connect to server`

**Solution**:
1. Check PostgreSQL service status
2. Verify database credentials
3. Ensure PostGIS extension is installed
4. Check network connectivity

#### Redis Connection Issues

**Problem**: `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solution**:
1. Check Redis service status
2. Verify Redis URL configuration
3. Check Redis memory usage
4. Restart Redis service if needed

#### Celery Task Issues

**Problem**: Background tasks not processing

**Solution**:
1. Check Celery worker status
2. Verify Redis broker connection
3. Check task queue status
4. Review Celery logs for errors

#### Payment Processing Issues

**Problem**: Payment failures or webhook issues

**Solution**:
1. Verify payment gateway credentials
2. Check webhook endpoint accessibility
3. Review payment logs
4. Test with sandbox environment

#### WebSocket Connection Issues

**Problem**: Real-time updates not working

**Solution**:
1. Check Django Channels configuration
2. Verify Redis channel layer
3. Check WebSocket URL routing
4. Review browser console for errors

### Performance Optimization

#### Database Optimization
- Add appropriate indexes
- Use database connection pooling
- Optimize query patterns
- Regular VACUUM and ANALYZE

#### Caching Strategy
- Cache frequently accessed data
- Use Redis for session storage
- Implement API response caching
- Cache static assets with CDN

#### Frontend Optimization
- Code splitting and lazy loading
- Image optimization
- Bundle size optimization
- Service worker for offline support

### Getting Help

1. **Documentation**: Check this documentation first
2. **Logs**: Review application and system logs
3. **Health Checks**: Use monitoring endpoints
4. **Community**: Check GitHub issues and discussions
5. **Support**: Contact technical support team

### Maintenance Tasks

#### Daily
- Monitor system health
- Check error logs
- Review performance metrics
- Verify backup completion

#### Weekly
- Update dependencies
- Review security alerts
- Analyze usage patterns
- Clean up old logs

#### Monthly
- Database maintenance
- Security audit
- Performance review
- Capacity planning

---

For more detailed information, see the specific documentation files in the `docs/` directory.