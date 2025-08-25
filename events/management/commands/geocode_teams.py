"""
Management Command um echte Koordinaten für Teams zu berechnen
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Team
from events.routing import get_route_calculator


class Command(BaseCommand):
    help = 'Berechnet echte Koordinaten für alle Teams basierend auf ihren Adressen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Überschreibt bereits vorhandene Koordinaten',
        )
        parser.add_argument(
            '--team-id',
            type=int,
            help='Nur für ein bestimmtes Team (by ID)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🗺️ Starte Geocoding für Teams...')
        )

        # Filter Teams
        teams_query = Team.objects.filter(is_active=True)
        
        if options['team_id']:
            teams_query = teams_query.filter(id=options['team_id'])
        elif not options['force']:
            # Nur Teams ohne Koordinaten
            teams_query = teams_query.filter(
                latitude__isnull=True, longitude__isnull=True
            )

        teams = list(teams_query)
        
        if not teams:
            self.stdout.write(
                self.style.WARNING('📍 Keine Teams zum Geocoding gefunden.')
            )
            return

        self.stdout.write(
            f'📊 Bearbeite {len(teams)} Teams...'
        )

        route_calculator = get_route_calculator()
        updated_count = 0

        with transaction.atomic():
            for team in teams:
                if not team.home_address:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ Team "{team.name}" hat keine Adresse')
                    )
                    continue

                # Berechne Koordinaten
                coords = route_calculator.get_coordinates_from_address(team.home_address)
                
                if coords:
                    lat, lng = coords
                    team.latitude = lat
                    team.longitude = lng
                    team.save(update_fields=['latitude', 'longitude'])
                    
                    updated_count += 1
                    self.stdout.write(
                        f'✅ {team.name}: {lat:.4f}, {lng:.4f}'
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'❌ Fehler bei Team "{team.name}"')
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'🎉 Geocoding abgeschlossen: {updated_count}/{len(teams)} Teams aktualisiert'
            )
        )
