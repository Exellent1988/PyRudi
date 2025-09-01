#!/usr/bin/env python3
"""
Simple script to run Django development server without Docker
"""
import os
import sys
import subprocess
import time

def check_service(host, port, service_name):
    """Check if a service is running"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        if result == 0:
            print(f"✅ {service_name} is running on {host}:{port}")
            return True
        else:
            print(f"❌ {service_name} is not running on {host}:{port}")
            return False
    except Exception as e:
        print(f"❌ Error checking {service_name}: {e}")
        return False

def main():
    print("🚀 Starting Running Dinner Development Server...")
    
    # Check if PostgreSQL is running
    if not check_service('localhost', 5432, 'PostgreSQL'):
        print("\n📋 Please start PostgreSQL first:")
        print("   Option 1: Use CodeSpace services (if available)")
        print("   Option 2: Install PostgreSQL locally")
        print("   Option 3: Use SQLite fallback")
        
        use_sqlite = input("\n❓ Use SQLite fallback? (y/N): ").lower().strip()
        if use_sqlite in ['y', 'yes']:
            # Update settings to use SQLite
            os.environ['USE_SQLITE'] = 'True'
            print("📦 Using SQLite fallback...")
        else:
            sys.exit(1)
    
    # Check if Redis is running (optional)
    if not check_service('localhost', 6379, 'Redis'):
        print("⚠️  Redis not available - using database for sessions")
        os.environ['USE_DB_SESSIONS'] = 'True'
    
    # Set development environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'running_dinner_app.settings')
    os.environ.setdefault('DEBUG', 'True')
    
    # Install dependencies if needed
    try:
        import django
    except ImportError:
        print("📦 Installing Python dependencies...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
    
    # Run migrations
    print("🗄️  Running database migrations...")
    subprocess.run([sys.executable, 'manage.py', 'migrate'])
    
    # Collect static files
    print("📦 Collecting static files...")
    subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'])
    
    # Start development server
    print("🎉 Starting Django development server...")
    print("📱 Server will be available at: http://localhost:8000")
    print("📍 Admin interface: http://localhost:8000/admin")
    
    try:
        subprocess.run([sys.executable, 'manage.py', 'runserver', '0.0.0.0:8000'])
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")

if __name__ == "__main__":
    main()
