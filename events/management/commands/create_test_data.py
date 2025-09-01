"""
Django management command to create large test datasets for performance testing
"""
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from accounts.models import CustomUser, Team, TeamMembership, DietaryRestriction
from events.models import Event, TeamRegistration
from optimization.models import OptimizationRun, TeamAssignment


class Command(BaseCommand):
    help = 'Create large test datasets for performance testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--teams',
            type=int,
            default=100,
            help='Number of teams to create (default: 100)',
        )
        parser.add_argument(
            '--events',
            type=int,
            default=5,
            help='Number of events to create (default: 5)',
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean existing test data first',
        )

    def handle(self, *args, **options):
        teams_count = options['teams']
        events_count = options['events']

        if options['clean']:
            self.clean_test_data()

        self.stdout.write(
            self.style.SUCCESS(
                f'🏗️  Creating test data: {teams_count} teams, {events_count} events...\n')
        )

        # Create test users and teams
        self.create_users_and_teams(teams_count)

        # Create test events
        self.create_events(events_count)

        # Create registrations
        self.create_registrations()

        # Create optimization data
        self.create_optimization_data()

        self.stdout.write(
            self.style.SUCCESS(f'✅ Test data created successfully!')
        )

        # Run performance test
        self.stdout.write('\n🚄 Running performance test with new data...')
        from django.core.management import call_command
        call_command('check_index_performance', '--benchmark')

    def clean_test_data(self):
        """Clean existing test data"""
        self.stdout.write('🧹 Cleaning existing test data...')

        # Delete test optimizations
        OptimizationRun.objects.filter(algorithm='test').delete()

        # Delete test registrations
        TeamRegistration.objects.filter(
            team__name__startswith='TestTeam').delete()

        # Delete test events
        Event.objects.filter(name__startswith='Test Event').delete()

        # Delete test teams
        Team.objects.filter(name__startswith='TestTeam').delete()

        # Delete test users
        CustomUser.objects.filter(username__startswith='testuser').delete()

        self.stdout.write(self.style.SUCCESS('✅ Test data cleaned'))

    def create_users_and_teams(self, teams_count):
        """Create test users and teams"""
        self.stdout.write(f'👥 Creating {teams_count} teams with users...')

        # Get or create dietary restrictions
        restrictions = list(DietaryRestriction.objects.all()[:10])

        # Munich coordinates for realistic geographic distribution
        munich_lat, munich_lng = 48.1351, 11.5820

        for i in range(teams_count):
            # Create team users
            user1 = CustomUser.objects.create_user(
                username=f'testuser{i*2+1}',
                email=f'testuser{i*2+1}@test.com',
                first_name=f'User{i*2+1}',
                last_name='Test',
                password='testpass123'
            )

            user2 = CustomUser.objects.create_user(
                username=f'testuser{i*2+2}',
                email=f'testuser{i*2+2}@test.com',
                first_name=f'User{i*2+2}',
                last_name='Test',
                password='testpass123'
            )

            # Add random dietary restrictions
            if restrictions and random.random() < 0.3:  # 30% have dietary restrictions
                user1.dietary_restrictions_structured.add(
                    random.choice(restrictions))
            if restrictions and random.random() < 0.3:
                user2.dietary_restrictions_structured.add(
                    random.choice(restrictions))

            # Create team
            # Distribute teams around Munich (±0.1 degrees = ~11km radius)
            lat_offset = (random.random() - 0.5) * 0.2
            lng_offset = (random.random() - 0.5) * 0.2

            team = Team.objects.create(
                name=f'TestTeam{i+1:04d}',
                description=f'Test team {i+1} for performance testing',
                contact_person=user1,
                home_address=f'Test Address {i+1}, Munich, Germany',
                latitude=Decimal(str(munich_lat + lat_offset)),
                longitude=Decimal(str(munich_lng + lng_offset)),
                max_guests=random.choice([4, 6, 8]),
                has_kitchen=random.choice(
                    [True, True, True, False]),  # 75% have kitchen
                participation_type=random.choice(
                    ['full', 'full', 'guest_only']),  # 80% full participation
            )

            # Add team memberships
            TeamMembership.objects.create(
                user=user1,
                team=team,
                role='leader',
                is_active=True
            )

            TeamMembership.objects.create(
                user=user2,
                team=team,
                role='member',
                is_active=True
            )

            if i % 100 == 0:  # Progress indicator
                self.stdout.write(f'  Created {i+1}/{teams_count} teams...')

    def create_events(self, events_count):
        """Create test events"""
        self.stdout.write(f'📅 Creating {events_count} test events...')

        # Get a staff user for organizer
        organizer = CustomUser.objects.filter(is_staff=True).first()
        if not organizer:
            organizer = CustomUser.objects.create_user(
                username='test_organizer',
                email='organizer@test.com',
                first_name='Test',
                last_name='Organizer',
                is_staff=True,
                password='testpass123'
            )

        for i in range(events_count):
            event_date = timezone.now().date() + timedelta(days=30 + i*7)

            event = Event.objects.create(
                name=f'Test Event {i+1:02d} - Performance Test',
                description=f'Large test event {i+1} with many teams for performance testing',
                organizer=organizer,
                event_date=event_date,
                registration_start=timezone.now() - timedelta(days=10),
                registration_deadline=timezone.now() + timedelta(days=20),
                max_teams=random.choice([50, 100, 200, 500]),
                team_size=2,
                groups_per_course=3,
                price_per_person=Decimal('25.00'),
                city='Munich',
                max_distance_km=Decimal('15.00'),
                status='registration_open',
                is_public=True
            )

    def create_registrations(self):
        """Create team registrations for events"""
        self.stdout.write('📝 Creating team registrations...')

        events = Event.objects.filter(name__startswith='Test Event')
        teams = Team.objects.filter(name__startswith='TestTeam')

        registration_count = 0
        for event in events:
            # Register 60-80% of teams for each event
            teams_to_register = random.sample(
                list(teams),
                k=min(int(len(teams) * random.uniform(0.6, 0.8)), event.max_teams)
            )

            for team in teams_to_register:
                TeamRegistration.objects.create(
                    event=event,
                    team=team,
                    status=random.choice(
                        ['confirmed', 'confirmed', 'confirmed', 'pending']),  # 75% confirmed
                    preferred_course=random.choice(
                        ['appetizer', 'main_course', 'dessert']),
                    can_host_appetizer=random.choice(
                        [True, True, False]),  # 66% can host
                    can_host_main_course=random.choice([True, True, False]),
                    can_host_dessert=random.choice([True, True, False]),
                    payment_status=random.choice(
                        ['paid', 'paid', 'pending']),  # 66% paid
                )
                registration_count += 1

        self.stdout.write(f'  Created {registration_count} registrations')

    def create_optimization_data(self):
        """Create optimization runs and team assignments"""
        self.stdout.write('🧮 Creating optimization results...')

        events = Event.objects.filter(name__startswith='Test Event')
        courses = ['appetizer', 'main_course', 'dessert']

        for event in events:
            # Create optimization run
            optimization_run = OptimizationRun.objects.create(
                event=event,
                status='completed',
                algorithm='test',
                started_at=timezone.now() - timedelta(minutes=30),
                completed_at=timezone.now() - timedelta(minutes=25),
                total_distance=Decimal(str(random.uniform(50.0, 200.0))),
                log_data={'test': 'performance test data'}
            )

            # Create team assignments
            confirmed_teams = list(
                event.team_registrations.filter(
                    status='confirmed').values_list('team', flat=True)
            )

            assignment_count = 0
            for i, team_id in enumerate(confirmed_teams):
                course = courses[i % 3]  # Distribute evenly across courses

                # Random host assignments (simplified)
                hosts = random.sample(confirmed_teams, k=3)

                TeamAssignment.objects.create(
                    optimization_run=optimization_run,
                    team_id=team_id,
                    course=course,
                    hosts_appetizer_id=hosts[0] if course != 'appetizer' else team_id,
                    hosts_main_course_id=hosts[1] if course != 'main_course' else team_id,
                    hosts_dessert_id=hosts[2] if course != 'dessert' else team_id,
                    distance_to_appetizer=Decimal(
                        str(random.uniform(0.5, 5.0))),
                    distance_to_main_course=Decimal(
                        str(random.uniform(0.5, 5.0))),
                    distance_to_dessert=Decimal(str(random.uniform(0.5, 5.0))),
                    total_distance=Decimal(str(random.uniform(2.0, 15.0))),
                )
                assignment_count += 1

            self.stdout.write(
                f'  Event "{event.name}": {assignment_count} assignments')
