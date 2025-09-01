"""
Django management command to check database index performance
"""
import time
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone
from events.models import Event, TeamRegistration
from accounts.models import Team
from optimization.models import OptimizationRun, TeamAssignment


class Command(BaseCommand):
    help = 'Check database index performance for Running Dinner queries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--benchmark',
            action='store_true',
            help='Run performance benchmarks',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed query information',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(
                '🚄 Running Database Index Performance Check...\n')
        )

        # Check if we're using PostgreSQL or SQLite
        db_engine = connection.settings_dict['ENGINE']
        if 'postgresql' in db_engine:
            self.stdout.write(self.style.SUCCESS(
                '✅ Using PostgreSQL - full index support'))
        elif 'sqlite' in db_engine:
            self.stdout.write(self.style.WARNING(
                '⚠️  Using SQLite - limited index support'))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Unknown database: {db_engine}'))

        self.stdout.write()

        # Run performance tests
        if options['benchmark']:
            self.run_benchmarks(options['verbose'])
        else:
            self.check_index_usage(options['verbose'])

    def run_benchmarks(self, verbose=False):
        """Run performance benchmarks for critical queries"""
        self.stdout.write(self.style.SUCCESS(
            '📊 Running Performance Benchmarks...\n'))

        benchmarks = [
            ('Event Status Filtering', self.benchmark_event_status),
            ('Team Registration Lookup', self.benchmark_team_registrations),
            ('Team Geographic Queries', self.benchmark_team_locations),
            ('Optimization Results', self.benchmark_optimization_results),
            ('Admin Dashboard Queries', self.benchmark_admin_queries),
        ]

        results = []
        for name, benchmark_func in benchmarks:
            self.stdout.write(f'⏱️  Testing: {name}...', ending='')

            start_time = time.time()
            count = benchmark_func()
            end_time = time.time()

            duration = (end_time - start_time) * \
                1000  # Convert to milliseconds
            results.append((name, duration, count))

            if duration < 50:
                status = self.style.SUCCESS(f' {duration:.1f}ms ✅')
            elif duration < 200:
                status = self.style.WARNING(f' {duration:.1f}ms ⚠️')
            else:
                status = self.style.ERROR(f' {duration:.1f}ms ❌')

            self.stdout.write(status)

        # Summary
        self.stdout.write('\n📈 Performance Summary:')
        self.stdout.write('=' * 60)
        for name, duration, count in results:
            self.stdout.write(
                f'{name:<30} {duration:>8.1f}ms ({count} records)')

        avg_time = sum(r[1] for r in results) / len(results)
        if avg_time < 50:
            self.stdout.write(self.style.SUCCESS(
                f'\n🎉 Excellent performance! Average: {avg_time:.1f}ms'))
        elif avg_time < 200:
            self.stdout.write(self.style.WARNING(
                f'\n⚠️  Good performance. Average: {avg_time:.1f}ms'))
        else:
            self.stdout.write(self.style.ERROR(
                f'\n❌ Poor performance. Average: {avg_time:.1f}ms'))

    def benchmark_event_status(self):
        """Benchmark event status filtering queries"""
        # Simulate typical event management queries
        events = Event.objects.filter(
            status='registration_open').select_related('organizer')
        return len(list(events))

    def benchmark_team_registrations(self):
        """Benchmark team registration queries"""
        # Simulate event management dashboard
        if Event.objects.exists():
            event = Event.objects.first()
            registrations = TeamRegistration.objects.filter(
                event=event, status='confirmed'
            ).select_related('team').prefetch_related('team__teammembership_set__user')
            return len(list(registrations))
        return 0

    def benchmark_team_locations(self):
        """Benchmark geographic team queries"""
        # Simulate optimization algorithm distance calculations
        teams = Team.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        )
        return len(list(teams))

    def benchmark_optimization_results(self):
        """Benchmark optimization result queries"""
        # Simulate optimization results viewing
        if OptimizationRun.objects.exists():
            latest_run = OptimizationRun.objects.filter(
                status='completed'
            ).order_by('-completed_at').first()

            if latest_run:
                assignments = TeamAssignment.objects.filter(
                    optimization_run=latest_run
                ).select_related('team', 'hosts_appetizer', 'hosts_main_course', 'hosts_dessert')
                return len(list(assignments))
        return 0

    def benchmark_admin_queries(self):
        """Benchmark admin dashboard queries"""
        # Simulate admin dashboard loading
        events = Event.objects.select_related('organizer').prefetch_related(
            'team_registrations__team'
        )
        return len(list(events))

    def check_index_usage(self, verbose=False):
        """Check index usage statistics (PostgreSQL only)"""
        self.stdout.write(self.style.SUCCESS('🔍 Checking Index Usage...\n'))

        db_engine = connection.settings_dict['ENGINE']
        if 'postgresql' not in db_engine:
            self.stdout.write(
                self.style.WARNING(
                    'Index usage statistics only available for PostgreSQL')
            )
            return

        with connection.cursor() as cursor:
            # Check index usage statistics
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
                LIMIT 20;
            """)

            results = cursor.fetchall()

            if results:
                self.stdout.write('📊 Most Used Indexes:')
                self.stdout.write('=' * 80)
                self.stdout.write(
                    f'{"Table":<25} {"Index":<35} {"Scans":<10} {"Reads"}')
                self.stdout.write('-' * 80)

                for row in results:
                    schema, table, index, scans, reads, fetches = row
                    self.stdout.write(
                        f'{table:<25} {index:<35} {scans:<10} {reads}')
            else:
                self.stdout.write(self.style.WARNING(
                    'No index usage statistics available'))

        # Check for unused indexes
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname
                FROM pg_stat_user_indexes 
                WHERE schemaname = 'public' 
                AND idx_scan = 0
                AND indexname NOT LIKE '%_pkey';
            """)

            unused = cursor.fetchall()
            if unused:
                self.stdout.write('\n⚠️  Potentially Unused Indexes:')
                self.stdout.write('=' * 50)
                for schema, table, index in unused:
                    self.stdout.write(f'{table}.{index}')
            else:
                self.stdout.write('\n✅ All indexes are being used')

        # Check slow queries
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    query,
                    calls,
                    mean_time,
                    total_time
                FROM pg_stat_statements 
                WHERE mean_time > 100
                ORDER BY mean_time DESC
                LIMIT 10;
            """)

            slow_queries = cursor.fetchall()
            if slow_queries:
                self.stdout.write('\n🐌 Slow Queries (>100ms average):')
                self.stdout.write('=' * 60)
                for query, calls, mean_time, total_time in slow_queries:
                    short_query = query[:50] + \
                        '...' if len(query) > 50 else query
                    self.stdout.write(f'{short_query:<53} {mean_time:>6.1f}ms')
            else:
                self.stdout.write('\n🚀 No slow queries detected')

        self.stdout.write('\n✅ Index performance check completed!')
