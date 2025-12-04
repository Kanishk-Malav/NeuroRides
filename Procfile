web: gunicorn neurorides.wsgi:application --config gunicorn.conf.py
release: python manage.py migrate --no-input && python manage.py collectstatic --no-input
