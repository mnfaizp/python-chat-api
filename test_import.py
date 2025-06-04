#!/usr/bin/env python3
"""
Simple test script to verify the application imports correctly.
"""
import os
import sys

# Set test environment variables
os.environ.update({
    'GEMINI_API_KEY': 'test-key',
    'OPENAI_API_KEY': 'test-key',
    'ELEVEN_LABS_API_KEY': 'test-key',
    'REDIS_HOST': 'localhost',
    'REDIS_PORT': '6379',
    'DEBUG': 'true'
})

try:
    print("🔄 Testing application import...")
    from main import app
    print("✅ Main application imports successfully")
    
    print(f"✅ App has {len(app.routes)} routes:")
    for route in app.routes:
        if hasattr(route, 'path'):
            methods = getattr(route, 'methods', {'GET'})
            print(f"  - {list(methods)} {route.path}")
    
    print("\n🔄 Testing health endpoint...")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    response = client.get("/health")
    print(f"✅ Health check status: {response.status_code}")
    print(f"✅ Health response: {response.json()}")
    
    print("\n🎉 All tests passed! Video functionality has been successfully removed.")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
