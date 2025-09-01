"""
Django management command für Redis Cache Monitoring
"""

import argparse

from django.core.cache import cache
from django.core.management.base import BaseCommand

from events.cache_signals import clear_all_event_caches, get_cache_health_status
from events.cache_utils import get_cache_stats, warm_cache_for_event


class Command(BaseCommand):
    help = 'Monitor and manage Redis cache for Running Dinner'

    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            action='store_true',
            help='Show cache health status',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show detailed cache statistics',
        )
        parser.add_argument(
            '--clear-event',
            type=int,
            help='Clear all caches for specific event ID',
        )
        parser.add_argument(
            '--warm-event',
            type=int,
            help='Warm cache for specific event ID',
        )
        parser.add_argument(
            '--clear-all',
            action='store_true',
            help='Clear all caches (use with caution!)',
        )
        parser.add_argument(
            '--test-cache',
            action='store_true',
            help='Test cache functionality',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Running Dinner Cache Monitor\n')
        )

        if options['status']:
            self.show_cache_status()
        
        elif options['stats']:
            self.show_cache_stats()
        
        elif options['clear_event']:
            self.clear_event_cache(options['clear_event'])
        
        elif options['warm_event']:
            self.warm_event_cache(options['warm_event'])
        
        elif options['clear_all']:
            self.clear_all_caches()
        
        elif options['test_cache']:
            self.test_cache_functionality()
        
        else:
            self.show_cache_status()

    def show_cache_status(self):
        """Show cache health status"""
        self.stdout.write(self.style.SUCCESS('📊 Cache Health Status'))
        self.stdout.write('=' * 50)
        
        health = get_cache_health_status()
        
        if health['status'] == 'healthy':
            status_style = self.style.SUCCESS
        elif health['status'] == 'warning':
            status_style = self.style.WARNING
        else:
            status_style = self.style.ERROR
        
        if 'error' in health:
            self.stdout.write(status_style(f"❌ Status: {health['status']}"))
            self.stdout.write(f"Error: {health['error']}")
        else:
            self.stdout.write(status_style(f"✅ Status: {health['status']}"))
            self.stdout.write(f"🎯 Hit Rate: {health['hit_rate']}%")
            self.stdout.write(f"💾 Memory Used: {health['memory_used']}")
            self.stdout.write(f"⚡ Ops/sec: {health['ops_per_sec']}")
            self.stdout.write(f"👥 Clients: {health['connected_clients']}")

    def show_cache_stats(self):
        """Show detailed cache statistics"""
        self.stdout.write(self.style.SUCCESS('📈 Detailed Cache Statistics'))
        self.stdout.write('=' * 50)
        
        try:
            stats = get_cache_stats()
            
            for key, value in stats.items():
                self.stdout.write(f"{key}: {value}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to get stats: {e}"))

    def clear_event_cache(self, event_id):
        """Clear all caches for specific event"""
        self.stdout.write(f"🧹 Clearing cache for event {event_id}...")
        
        try:
            clear_all_event_caches(event_id)
            self.stdout.write(self.style.SUCCESS(f"✅ Cache cleared for event {event_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to clear cache: {e}"))

    def warm_event_cache(self, event_id):
        """Warm cache for specific event"""
        self.stdout.write(f"🔥 Warming cache for event {event_id}...")
        
        try:
            warm_cache_for_event(event_id)
            self.stdout.write(self.style.SUCCESS(f"✅ Cache warmed for event {event_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to warm cache: {e}"))

    def clear_all_caches(self):
        """Clear all caches"""
        confirm = input("⚠️  Are you sure you want to clear ALL caches? (yes/no): ")
        
        if confirm.lower() != 'yes':
            self.stdout.write("Operation cancelled.")
            return
        
        self.stdout.write("🧹 Clearing all caches...")
        
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS("✅ All caches cleared"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to clear caches: {e}"))

    def test_cache_functionality(self):
        """Test basic cache functionality"""
        self.stdout.write(self.style.SUCCESS('🧪 Testing Cache Functionality'))
        self.stdout.write('=' * 50)
        
        # Test 1: Basic Set/Get
        test_key = 'test_cache_functionality'
        test_value = {'message': 'Hello Redis!', 'timestamp': 'now'}
        
        try:
            cache.set(test_key, test_value, 60)
            retrieved = cache.get(test_key)
            
            if retrieved == test_value:
                self.stdout.write(self.style.SUCCESS("✅ Basic cache set/get: PASSED"))
            else:
                self.stdout.write(self.style.ERROR("❌ Basic cache set/get: FAILED"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Basic cache test failed: {e}"))
        
        # Test 2: Cache Key Generation
        try:
            from events.cache_utils import generate_cache_key
            
            key1 = generate_cache_key('test', 'param1', 'param2')
            key2 = generate_cache_key('test', 'param1', 'param2')
            key3 = generate_cache_key('test', 'param1', 'different')
            
            if key1 == key2 and key1 != key3:
                self.stdout.write(self.style.SUCCESS("✅ Cache key generation: PASSED"))
            else:
                self.stdout.write(self.style.ERROR("❌ Cache key generation: FAILED"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Cache key test failed: {e}"))
        
        # Test 3: Cache Managers
        try:
            from events.cache_utils import EventCacheManager

            # Test event summary cache
            test_data = {'event_id': 999, 'test': True}
            EventCacheManager.set_event_summary(999, test_data)
            retrieved = EventCacheManager.get_event_summary(999)
            
            if retrieved == test_data:
                self.stdout.write(self.style.SUCCESS("✅ Cache managers: PASSED"))
            else:
                self.stdout.write(self.style.ERROR("❌ Cache managers: FAILED"))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Cache manager test failed: {e}"))
        
        # Cleanup
        try:
            cache.delete(test_key)
            EventCacheManager.invalidate_event_cache(999)
        except:
            pass
        
        self.stdout.write("\n🎉 Cache testing completed!")
