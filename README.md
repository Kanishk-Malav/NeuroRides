# NeuroRides - Robotaxi Fleet Management Platform

A full-stack Django-based robotaxi fleet management platform prototype with real-time tracking, intelligent dispatch, secure payments, and comprehensive fleet management.

## Features

- **User Authentication**: JWT-based authentication with role-based access (Rider, Operator, Admin)
- **Ride Booking**: Map-based ride booking with fare estimation
- **Intelligent Dispatch**: Nearest vehicle assignment using PostGIS
- **Real-time Tracking**: WebSocket-based live vehicle and ride tracking
- **Fleet Management**: Vehicle monitoring, telemetry, and maintenance scheduling
- **Secure Payments**: Stripe and Razorpay integration (sandbox mode)
- **Analytics Dashboard**: Real-time KPIs and reporting
- **Background Tasks**: Celery-based async processing

## Tech Stack

### Backend
- Django 5.0 + Django REST Framework
- PostGIS (PostgreSQL with spatial extensions)
- Redis (caching and message broker)
- Celery (background tasks)
- Django Channels (WebSockets)
- JWT Authentication

### Frontend (Coming Soon)
- React + TypeScript
- TailwindCSS
- Leaflet (maps)
- Recharts (analytics)

### Infrastructure
- Docker + Docker Compose
- Nginx (load balancer)
- PostgreSQL + PostGIS
- Redis

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL with PostGIS extension
- Redis
- Docker (optional)

### Local Development

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd neurorides
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your database and API keys
   ```

3. **Database Setup**
   ```bash
   # Create PostgreSQL database with PostGIS
   createdb neurorides_db
   psql neurorides_db -c "CREATE EXTENSION postgis;"
   
   # Run migrations
   python manage.py migrate
   ```

4. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run Development Server**
   ```bash
   # Terminal 1: Django server
   python manage.py runserver
   
   # Terminal 2: Celery worker
   celery -A neurorides worker --loglevel=info
   
   # Terminal 3: Celery beat
   celery -A neurorides beat --loglevel=info
   ```

### Docker Development

```bash
# Build and run with Docker Compose
docker-compose up --build

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

## API Documentation

Once the server is running, visit:
- API Documentation: http://localhost:8000/api/schema/swagger-ui/
- Admin Panel: http://localhost:8000/admin/

## Project Structure

```
neurorides/
├── accounts/          # User authentication and profiles
├── rides/             # Ride booking and management
├── fleet/             # Vehicle and telemetry management
├── dispatch/          # Intelligent vehicle assignment
├── payments/          # Payment processing
├── analytics/         # Data aggregation and reporting
├── notifications/     # WebSocket consumers
├── neurorides/        # Django project settings
├── static/            # Static files
├── templates/         # Django templates
├── logs/              # Application logs
├── docker-compose.yml # Docker configuration
├── Dockerfile         # Docker image
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Development Status

- [x] Project structure and configuration
- [ ] User authentication system
- [ ] Fleet management system
- [ ] Ride booking system
- [ ] Intelligent dispatch
- [ ] Real-time WebSockets
- [ ] Payment integration
- [ ] Analytics system
- [ ] React frontend
- [ ] Background tasks
- [ ] Logging and monitoring
- [ ] Deployment configuration

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contact

For questions or support, please contact the development team.