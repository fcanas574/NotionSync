#!/usr/bin/env python3
"""
Verification script for Django web application migration.
Tests that the web app can start and basic functionality works.
"""
import sys
import os
import django

# Setup Django
sys.path.insert(0, '/home/runner/work/NotionSync/NotionSync')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'notionsync_web.settings')
django.setup()

from django.contrib.auth.models import User
from sync.models import UserProfile, SyncLog
from sync.services import SyncService

def test_models():
    """Test that models can be created."""
    print("Testing models...")
    
    # Create a test user
    user = User.objects.create_user(username='testuser', password='testpass123')
    print(f"✓ Created user: {user.username}")
    
    # Create profile
    profile = UserProfile.objects.create(
        user=user,
        canvas_api_key='test_key',
        notion_api_key='test_notion_key',
        notion_database_id='a' * 32,
        sync_buckets=['upcoming', 'future']
    )
    print(f"✓ Created profile for: {profile.user.username}")
    
    # Create sync log
    log = SyncLog.objects.create(
        user=user,
        status='success',
        message='Test sync',
        assignments_synced=5
    )
    print(f"✓ Created sync log: {log.id}")
    
    # Verify retrieval
    assert UserProfile.objects.filter(user=user).exists()
    assert SyncLog.objects.filter(user=user).exists()
    print("✓ Models can be retrieved")
    
    # Cleanup
    user.delete()
    print("✓ Cleanup complete")
    
    return True

def test_services():
    """Test that service layer is accessible."""
    print("\nTesting services...")
    
    # Check that SyncService exists and has required methods
    assert hasattr(SyncService, 'sync_assignments')
    assert hasattr(SyncService, 'get_courses')
    print("✓ SyncService has required methods")
    
    return True

def test_urls():
    """Test that URL configuration is correct."""
    print("\nTesting URL configuration...")
    
    from django.urls import reverse
    
    # Test that all main URLs can be reversed
    urls_to_test = [
        'dashboard',
        'login',
        'register',
        'settings',
        'run_sync',
        'sync_history',
        'logout',
    ]
    
    for url_name in urls_to_test:
        try:
            url = reverse(url_name)
            print(f"✓ URL '{url_name}' resolves to: {url}")
        except Exception as e:
            print(f"✗ URL '{url_name}' failed: {e}")
            return False
    
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Django Web Application Verification")
    print("=" * 60)
    
    tests = [
        test_models,
        test_services,
        test_urls,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 60)
    if all(results):
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    else:
        print("✗ Some tests failed")
        print("=" * 60)
        return 1

if __name__ == '__main__':
    sys.exit(main())
