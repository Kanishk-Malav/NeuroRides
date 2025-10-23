#!/usr/bin/env python
"""
Quick test script to verify NeuroRides platform is running correctly.
"""

import os
import sys
import django
import requests
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neurorides.settings')
django.setup()

def test_backend():
    """Test backend services."""
    print("🔍 Testing Backend Services...")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost:8000/health/', timeout=5)
        if response.status_code == 200:
            print("✅ Backend health check: PASSED")
        else:
            print(f"❌ Backend health check: FAILED (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend health check: FAILED (Error: {e})")
    
    try:
        # Test API endpoint
        response = requests.get('http://localhost:8000/api/', timeout=5)
        if response.status_code in [200, 404]:  # 404 is OK for root API
            print("✅ API endpoint: ACCESSIBLE")
        else:
            print(f"❌ API endpoint: FAILED (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ API endpoint: FAILED (Error: {e})")

def test_frontend():
    """Test frontend service."""
    print("\n🔍 Testing Frontend Service...")
    
    try:
        response = requests.get('http://localhost:3000', timeout=5)
        if response.status_code == 200:
            print("✅ Frontend: ACCESSIBLE")
        else:
            print(f"❌ Frontend: FAILED (Status: {response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend: FAILED (Error: {e})")

def test_database():
    """Test database connection."""
    print("\n🔍 Testing Database Connection...")
    
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result[0] == 1:
                print("✅ Database connection: WORKING")
            else:
                print("❌ Database connection: FAILED")
    except Exception as e:
        print(f"❌ Database connection: FAILED (Error: {e})")

def test_redis():
    """Test Redis connection."""
    print("\n🔍 Testing Redis Connection...")
    
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 30)
        value = cache.get('test_key')
        if value == 'test_value':
            print("✅ Redis connection: WORKING")
        else:
            print("❌ Redis connection: FAILED")
    except Exception as e:
        print(f"❌ Redis connection: FAILED (Error: {e})")

def test_sample_data():
    """Test if sample data exists."""
    print("\n🔍 Testing Sample Data...")
    
    try:
        from accounts.models import User
        from fleet.models import Vehicle
        
        user_count = User.objects.count()
        vehicle_count = Vehicle.objects.count()
        
        print(f"📊 Users in database: {user_count}")
        print(f"🚗 Vehicles in database: {vehicle_count}")
        
        if user_count > 0:
            print("✅ Sample users: CREATED")
        else:
            print("⚠️  Sample users: NOT FOUND (Run: python manage.py create_initial_users)")
            
        if vehicle_count > 0:
            print("✅ Sample vehicles: CREATED")
        else:
            print("⚠️  Sample vehicles: NOT FOUND (Run: python manage.py create_sample_fleet)")
            
    except Exception as e:
        print(f"❌ Sample data check: FAILED (Error: {e})")

def main():
    """Run all tests."""
    print("🚀 NeuroRides Platform Quick Test")
    print("=" * 40)
    
    test_database()
    test_redis()
    test_sample_data()
    test_backend()
    test_frontend()
    
    print("\n" + "=" * 40)
    print("🎯 Test Summary:")
    print("If all tests show ✅, your platform is ready!")
    print("If you see ❌ or ⚠️, check the error messages above.")
    print("\n📖 Next steps:")
    print("1. Open http://localhost:3000 for the frontend")
    print("2. Open http://localhost:8000/admin for admin panel")
    print("3. Check docs/README.md for detailed usage guide")

if __name__ == '__main__':
    main()