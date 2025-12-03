#!/bin/bash
set -e

echo "Starting NeuroRides container..."

# Run database migrations (safe)
echo "Running migrations..."
python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "Checking superuser..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@neurorides.com', 'admin123')
    print('Superuser created')
else:
    print('Superuser already exists')
EOF

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Load initial data if needed
if [ "$LOAD_INITIAL_DATA" = "true" ]; then
    echo "Loading initial data..."
    python manage.py create_initial_users
    python manage.py create_sample_fleet
    python manage.py setup_payment_gateways
fi

echo "Starting application..."
exec "$@"