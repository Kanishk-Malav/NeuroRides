#!/usr/bin/env python
"""
Troubleshooting script for NeuroRides platform.
"""

import os
import subprocess
import sys

def check_docker():
    """Check Docker installation."""
    print("🐳 Checking Docker...")
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker: {result.stdout.strip()}")
        else:
            print("❌ Docker: Not installed or not working")
            return False
    except FileNotFoundError:
        print("❌ Docker: Not installed")
        return False
    
    try:
        result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Docker Compose: {result.stdout.strip()}")
        else:
            print("❌ Docker Compose: Not installed or not working")
            return False
    except FileNotFoundError:
        print("❌ Docker Compose: Not installed")
        return False
    
    return True

def check_python():
    """Check Python installation."""
    print("\n🐍 Checking Python...")
    version = sys.version_info
    print(f"✅ Python: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("⚠️  Warning: Python 3.8+ recommended")
    
    return True

def check_node():
    """Check Node.js installation."""
    print("\n📦 Checking Node.js...")
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Node.js: {result.stdout.strip()}")
        else:
            print("❌ Node.js: Not installed or not working")
            return False
    except FileNotFoundError:
        print("❌ Node.js: Not installed")
        return False
    
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ npm: {result.stdout.strip()}")
        else:
            print("❌ npm: Not installed or not working")
            return False
    except FileNotFoundError:
        print("❌ npm: Not installed")
        return False
    
    return True

def check_ports():
    """Check if required ports are available."""
    print("\n🔌 Checking Ports...")
    
    import socket
    
    ports = {
        3000: "Frontend (React)",
        8000: "Backend (Django)",
        5432: "Database (PostgreSQL)",
        6379: "Cache (Redis)"
    }
    
    for port, service in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"⚠️  Port {port} ({service}): IN USE")
        else:
            print(f"✅ Port {port} ({service}): AVAILABLE")

def check_files():
    """Check if required files exist."""
    print("\n📁 Checking Required Files...")
    
    required_files = [
        'manage.py',
        'requirements.txt',
        'docker-compose.yml',
        '.env.example',
        'frontend/package.json'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}: EXISTS")
        else:
            print(f"❌ {file_path}: MISSING")

def provide_solutions():
    """Provide common solutions."""
    print("\n🔧 Common Solutions:")
    print("=" * 40)
    
    print("\n1. If Docker is not installed:")
    print("   - macOS: brew install docker docker-compose")
    print("   - Ubuntu: sudo apt install docker.io docker-compose")
    print("   - Windows: Download Docker Desktop")
    
    print("\n2. If ports are in use:")
    print("   - Stop conflicting services")
    print("   - Or modify ports in docker-compose.yml")
    
    print("\n3. If .env file is missing:")
    print("   - Run: cp .env.example .env")
    
    print("\n4. If database connection fails:")
    print("   - Ensure PostgreSQL is running")
    print("   - Check DATABASE_URL in .env")
    
    print("\n5. If frontend won't start:")
    print("   - cd frontend && npm install")
    print("   - Check Node.js version (14+ required)")

def main():
    """Run all checks."""
    print("🔍 NeuroRides Platform Troubleshooting")
    print("=" * 40)
    
    all_good = True
    
    all_good &= check_docker()
    all_good &= check_python()
    all_good &= check_node()
    check_ports()
    check_files()
    
    if all_good:
        print("\n🎉 All system checks passed!")
        print("You should be able to run the platform.")
    else:
        print("\n⚠️  Some issues found. Check the solutions below.")
    
    provide_solutions()

if __name__ == '__main__':
    main()