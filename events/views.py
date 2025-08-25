from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
import json
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.db import models
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from .models import Event, Course, TeamRegistration, EventOrganizer
from accounts.models import Team, TeamMembership
from optimization.models import OptimizationRun


# REST API ViewSets
class EventViewSet(viewsets.ModelViewSet):
    """API ViewSet für Event-Management"""
    queryset = Event.objects.all()
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtere Events basierend auf User-Berechtigung"""
        user = self.request.user
        if user.is_staff:
            return Event.objects.all()

        # Zeige öffentliche Events und Events wo User als Organisator oder Team-Mitglied registriert ist
        return Event.objects.filter(
            Q(is_public=True) |
            Q(organizer=user) |
            Q(team_registrations__team__members=user)
        ).distinct()

    def perform_create(self, serializer):
        """Setze aktuellen User als Organisator"""
        serializer.save(organizer=self.request.user)

    @action(detail=True, methods=['post'])
    def register_team(self, request, pk=None):
        """Registriere Team für Event"""
        event = self.get_object()
        team_id = request.data.get('team_id')

        if not team_id:
            return Response({'error': 'team_id ist erforderlich'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            team = Team.objects.get(id=team_id)

            # Prüfe ob User berechtigt ist das Team zu registrieren
            membership = TeamMembership.objects.filter(
                user=request.user, team=team, role__in=['leader', 'member'], is_active=True
            ).first()

            if not membership:
                return Response(
                    {'error': 'Sie sind nicht berechtigt dieses Team zu registrieren'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Prüfe ob Anmeldung noch offen ist
            if not event.is_registration_open:
                return Response(
                    {'error': 'Anmeldung für dieses Event ist nicht mehr möglich'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Prüfe ob Team bereits registriert ist
            if TeamRegistration.objects.filter(event=event, team=team).exists():
                return Response(
                    {'error': 'Team ist bereits für dieses Event registriert'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Erstelle Registrierung
            registration = TeamRegistration.objects.create(
                event=event,
                team=team,
                preferred_course=request.data.get('preferred_course'),
                can_host_appetizer=request.data.get(
                    'can_host_appetizer', True),
                can_host_main_course=request.data.get(
                    'can_host_main_course', True),
                can_host_dessert=request.data.get('can_host_dessert', True)
            )

            return Response({
                'message': 'Team erfolgreich registriert',
                'registration_id': registration.id
            }, status=status.HTTP_201_CREATED)

        except Team.DoesNotExist:
            return Response({'error': 'Team nicht gefunden'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def registrations(self, request, pk=None):
        """Hole alle Registrierungen für ein Event"""
        event = self.get_object()

        # Nur Organisator kann alle Registrierungen sehen
        if event.organizer != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Keine Berechtigung'},
                status=status.HTTP_403_FORBIDDEN
            )

        registrations = TeamRegistration.objects.filter(event=event)
        registration_data = []

        for reg in registrations:
            registration_data.append({
                'id': reg.id,
                'team_name': reg.team.name,
                'team_id': reg.team.id,
                'status': reg.status,
                'preferred_course': reg.preferred_course,
                'can_host_appetizer': reg.can_host_appetizer,
                'can_host_main_course': reg.can_host_main_course,
                'can_host_dessert': reg.can_host_dessert,
                'payment_status': reg.payment_status,
                'registered_at': reg.registered_at,
            })

        return Response(registration_data)


# Django Views
def event_list(request):
    """Liste aller öffentlichen Events"""
    events = Event.objects.filter(is_public=True).order_by('-event_date')

    # Filter anwenden
    city_filter = request.GET.get('city')
    search_query = request.GET.get('search')

    if city_filter:
        events = events.filter(city__iexact=city_filter)

    if search_query:
        events = events.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(city__icontains=search_query)
        )

    # Verfügbare Städte für Filter
    available_cities = Event.objects.filter(is_public=True).values_list(
        'city', flat=True).distinct().order_by('city')

    context = {
        'events': events,
        'available_cities': available_cities,
        'current_city_filter': city_filter,
        'current_search': search_query,
    }
    return render(request, 'events/event_list.html', context)


def event_detail(request, event_id):
    """Event-Detail-Ansicht"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.is_public and event.organizer != request.user and not request.user.is_staff:
        messages.error(
            request, 'Sie haben keine Berechtigung dieses Event zu sehen.')
        return redirect('events:event_list')

    user_teams = None
    user_registrations = None

    if request.user.is_authenticated:
        user_teams = Team.objects.filter(
            teammembership__user=request.user,
            teammembership__is_active=True,
            is_active=True
        )
        user_registrations = TeamRegistration.objects.filter(
            event=event,
            team__teammembership__user=request.user,
            team__teammembership__is_active=True
        )
        # Liste der angemeldeten Teams für Template-Vergleich
        registered_team_ids = list(
            user_registrations.values_list('team_id', flat=True))

    context = {
        'event': event,
        'user_teams': user_teams,
        'user_registrations': user_registrations,
        'is_organizer': request.user.is_authenticated and event.can_user_manage_event(request.user),
        'user_role': event.get_organizer_role(request.user) if request.user.is_authenticated else None,
    }
    return render(request, 'events/event_detail.html', context)


# Event Management Views (Frontend statt Admin)
@login_required
def organizer_dashboard(request):
    """Dashboard für Event-Organisatoren"""
    # Alle Events wo User Organisator ist (Haupt- oder Co-Organisator)
    all_events = Event.objects.filter(
        Q(organizer=request.user) |
        Q(eventorganizer__user=request.user, eventorganizer__is_active=True)
    ).distinct().order_by('-created_at')

    # Statistiken
    total_events = all_events.count()
    active_events = all_events.filter(
        status__in=['planning', 'registration_open', 'registration_closed']).count()
    total_teams = TeamRegistration.objects.filter(event__in=all_events).count()

    # Füge Berechtigungen zu jedem Event hinzu für Templates
    events_with_permissions = []
    for event in all_events:
        event.user_can_manage = event.can_user_manage_event(request.user)
        event.user_role_display = event.get_organizer_role(request.user)
        events_with_permissions.append(event)

    context = {
        'events': events_with_permissions,
        'stats': {
            'total_events': total_events,
            'active_events': active_events,
            'total_teams': total_teams,
        }
    }
    return render(request, 'events/organizer_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/login/')
def create_event(request):
    """Event erstellen - schönes Frontend"""
    if request.method == 'POST':
        try:
            from datetime import datetime

            event = Event.objects.create(
                name=request.POST.get('name'),
                description=request.POST.get('description'),
                organizer=request.user,
                event_date=request.POST.get('event_date'),
                registration_start=request.POST.get('registration_start'),
                registration_deadline=request.POST.get(
                    'registration_deadline'),
                appetizer_time=request.POST.get('appetizer_time', '18:00'),
                main_course_time=request.POST.get('main_course_time', '20:00'),
                dessert_time=request.POST.get('dessert_time', '22:00'),
                city=request.POST.get('city'),
                max_teams=int(request.POST.get('max_teams', 12)),
                team_size=int(request.POST.get('team_size', 2)),
                groups_per_course=int(
                    request.POST.get('groups_per_course', 3)),
                price_per_person=request.POST.get('price_per_person', '25.00'),
                max_distance_km=request.POST.get('max_distance_km', '10.00'),
                is_public=request.POST.get('is_public') == 'on'
            )

            messages.success(
                request, f'Event "{event.name}" wurde erfolgreich erstellt!')
            return redirect('events:manage_event', event_id=event.id)

        except Exception as e:
            messages.error(
                request, f'Fehler beim Erstellen des Events: {str(e)}')

    return render(request, 'events/create_event.html')


@login_required
def manage_event(request, event_id):
    """Event-Management Interface"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.can_user_manage_event(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, dieses Event zu verwalten.')
        return redirect('events:event_detail', event_id=event_id)

    # Hole Event-Daten
    registrations = TeamRegistration.objects.filter(
        event=event).select_related('team')
    organizers = EventOrganizer.objects.filter(
        event=event, is_active=True).select_related('user')

    # Statistiken
    confirmed_teams = registrations.filter(status='confirmed').count()
    pending_teams = registrations.filter(status='pending').count()
    total_participants = sum(
        reg.team.member_count for reg in registrations.filter(status='confirmed'))

    # Allergie-Übersicht
    critical_allergies = []
    for reg in registrations.filter(status='confirmed'):
        team_critical = reg.team.get_team_emergency_info()
        if team_critical:
            critical_allergies.extend(team_critical)

    # Berechtige Benutzer-Aktionen für Template
    user_can_manage_teams = event.can_user_manage_teams(request.user)
    user_can_run_optimization = event.can_user_run_optimization(request.user)

    context = {
        'event': event,
        'registrations': registrations,
        'organizers': organizers,
        'user_role': event.get_organizer_role(request.user),
        'user_can_manage_teams': user_can_manage_teams,
        'user_can_run_optimization': user_can_run_optimization,
        'stats': {
            'confirmed_teams': confirmed_teams,
            'pending_teams': pending_teams,
            'total_participants': total_participants,
            'critical_allergies_count': len(critical_allergies),
            'registration_progress': (confirmed_teams / event.max_teams * 100) if event.max_teams > 0 else 0
        },
        'critical_allergies': critical_allergies,
    }
    return render(request, 'events/manage_event.html', context)


@login_required
@require_http_methods(["POST"])
def update_event(request, event_id):
    """Event aktualisieren - nur Haupt-Organisator"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung - nur Haupt-Organisator kann Event bearbeiten
    if event.organizer != request.user:
        messages.error(
            request, 'Nur der Haupt-Organisator kann das Event bearbeiten.')
        return redirect('events:manage_event', event_id=event_id)

    try:
        # Update Event-Daten
        event.name = request.POST.get('name')
        event.description = request.POST.get('description')
        event.city = request.POST.get('city')
        event.event_date = request.POST.get('event_date')
        event.max_teams = int(request.POST.get('max_teams'))
        event.price_per_person = request.POST.get('price_per_person')
        event.appetizer_time = request.POST.get('appetizer_time')
        event.main_course_time = request.POST.get('main_course_time')
        event.dessert_time = request.POST.get('dessert_time')
        event.status = request.POST.get('status')
        event.is_public = request.POST.get('is_public') == 'on'

        event.save()

        messages.success(
            request, f'Event "{event.name}" wurde erfolgreich aktualisiert!')

    except Exception as e:
        messages.error(
            request, f'Fehler beim Aktualisieren des Events: {str(e)}')

    return redirect('events:manage_event', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def invite_organizer(request, event_id):
    """Co-Organisator einladen"""
    event = get_object_or_404(Event, id=event_id)

    # Nur Hauptorganisator oder Admins können neue Organisatoren einladen
    if request.user != event.organizer:
        try:
            organizer_role = EventOrganizer.objects.get(
                event=event, user=request.user, is_active=True)
            if not organizer_role.has_permission('manage_organizers'):
                messages.error(
                    request, 'Sie haben keine Berechtigung, Organisatoren einzuladen.')
                return redirect('events:manage_event', event_id=event_id)
        except EventOrganizer.DoesNotExist:
            messages.error(
                request, 'Sie haben keine Berechtigung, Organisatoren einzuladen.')
            return redirect('events:manage_event', event_id=event_id)

    email = request.POST.get('email')
    role = request.POST.get('role', 'assistant')
    permissions = request.POST.getlist('permissions')

    try:
        from accounts.models import CustomUser
        invited_user = CustomUser.objects.get(email=email)

        # Prüfe ob bereits Organisator
        if EventOrganizer.objects.filter(event=event, user=invited_user).exists():
            messages.warning(
                request, f'{invited_user.full_name} ist bereits Organisator dieses Events.')
            return redirect('events:manage_event', event_id=event_id)

        # Erstelle Organisator-Rolle
        EventOrganizer.objects.create(
            event=event,
            user=invited_user,
            role=role,
            permissions=permissions,
            invited_by=request.user
        )

        messages.success(
            request, f'{invited_user.full_name} wurde als {role} hinzugefügt!')

    except CustomUser.DoesNotExist:
        messages.error(request, f'Kein User mit der E-Mail {email} gefunden.')

    return redirect('events:manage_event', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def update_team_status(request, event_id, registration_id):
    """Team-Anmeldestatus aktualisieren"""
    event = get_object_or_404(Event, id=event_id)
    registration = get_object_or_404(
        TeamRegistration, id=registration_id, event=event)

    if not event.can_user_manage_teams(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, Teams zu verwalten.')
        return redirect('events:manage_event', event_id=event_id)

    new_status = request.POST.get('status')
    if new_status in [choice[0] for choice in TeamRegistration.STATUS_CHOICES]:
        old_status = registration.get_status_display()
        registration.status = new_status
        registration.save()

        messages.success(
            request,
            f'Status von Team "{registration.team.name}" von "{old_status}" zu "{registration.get_status_display()}" geändert.'
        )
    else:
        messages.error(request, 'Ungültiger Status.')

    return redirect('events:manage_event', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def register_team(request, event_id):
    """Team für Event anmelden"""
    event = get_object_or_404(Event, id=event_id)
    team_id = request.POST.get('team_id')

    if not team_id:
        messages.error(request, 'Bitte wähle ein Team aus.')
        return redirect('events:event_detail', event_id=event_id)

    team = get_object_or_404(Team, id=team_id)

    # Prüfe ob User Berechtigung für dieses Team hat
    if not TeamMembership.objects.filter(user=request.user, team=team, is_active=True).exists():
        messages.error(request, 'Du hast keine Berechtigung für dieses Team.')
        return redirect('events:event_detail', event_id=event_id)

    # Prüfe ob Anmeldung offen ist
    if not event.is_registration_open:
        messages.error(
            request, 'Die Anmeldung für dieses Event ist nicht mehr möglich.')
        return redirect('events:event_detail', event_id=event_id)

    # Prüfe ob Team bereits angemeldet ist
    if TeamRegistration.objects.filter(event=event, team=team).exists():
        messages.warning(
            request, f'Team "{team.name}" ist bereits für dieses Event angemeldet.')
        return redirect('events:event_detail', event_id=event_id)

    # Prüfe Event-Kapazität
    confirmed_count = TeamRegistration.objects.filter(
        event=event,
        status__in=['confirmed', 'pending']
    ).count()

    if confirmed_count >= event.max_teams:
        status = 'waiting_list'
        messages.info(
            request, f'Event ist voll - Team "{team.name}" wurde auf die Warteliste gesetzt.')
    else:
        status = 'pending'
        messages.success(
            request, f'Team "{team.name}" wurde erfolgreich angemeldet!')

    # Erstelle Team-Registrierung
    TeamRegistration.objects.create(
        event=event,
        team=team,
        status=status,
        preferred_course=request.POST.get('preferred_course', 'main_course'),
        can_host_appetizer=request.POST.get('can_host_appetizer') == 'on',
        can_host_main_course=request.POST.get('can_host_main_course') == 'on',
        can_host_dessert=request.POST.get('can_host_dessert') == 'on',
        payment_status='pending'
    )

    return redirect('events:event_detail', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def unregister_team(request, event_id):
    """Team-Anmeldung stornieren"""
    event = get_object_or_404(Event, id=event_id)
    team_id = request.POST.get('team_id')

    if not team_id:
        messages.error(request, 'Bitte wähle ein Team aus.')
        return redirect('events:event_detail', event_id=event_id)

    team = get_object_or_404(Team, id=team_id)

    # Prüfe Berechtigung
    if not TeamMembership.objects.filter(user=request.user, team=team, is_active=True).exists():
        messages.error(request, 'Du hast keine Berechtigung für dieses Team.')
        return redirect('events:event_detail', event_id=event_id)

    try:
        registration = TeamRegistration.objects.get(event=event, team=team)

        # Prüfe ob Stornierung noch möglich
        from datetime import datetime
        from django.utils import timezone
        if event.registration_deadline < timezone.now():
            messages.error(
                request, 'Stornierung nach Anmeldeschluss nicht mehr möglich.')
            return redirect('events:event_detail', event_id=event_id)

        registration.delete()
        messages.success(
            request, f'Anmeldung von Team "{team.name}" wurde storniert.')

    except TeamRegistration.DoesNotExist:
        messages.error(request, 'Team ist nicht für dieses Event angemeldet.')

    return redirect('events:event_detail', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def start_optimization(request, event_id):
    """Startet die Optimierung für das Event"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.can_user_run_optimization(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, die Optimierung zu starten.')
        return redirect('events:manage_event', event_id=event_id)

    # Prüfe ob genügend Teams angemeldet sind
    confirmed_teams = event.team_registrations.filter(
        status='confirmed').count()
    if confirmed_teams < 3:
        messages.error(
            request, f'Mindestens 3 bestätigte Teams erforderlich. Aktuell: {confirmed_teams}')
        return redirect('events:manage_event', event_id=event_id)

    try:
        # Setze Status auf "Optimierung läuft"
        event.status = 'optimization_running'
        event.save()

        # Lösche alle alten OptimizationRuns und TeamAssignments für dieses Event
        from optimization.models import OptimizationRun, TeamAssignment
        from django.utils import timezone
        from .optimization import RunningDinnerOptimizer
        import logging

        logger = logging.getLogger(__name__)

        # Lösche alte Optimierungen
        old_runs = OptimizationRun.objects.filter(event=event)
        old_assignments_count = TeamAssignment.objects.filter(
            optimization_run__event=event).count()
        old_runs.delete()  # Löscht auch TeamAssignments durch CASCADE

        logger.info(
            f"🗑️ {old_assignments_count} alte Team-Zuweisungen gelöscht")

        # Erstelle und konfiguriere Optimizer
        optimizer = RunningDinnerOptimizer(event)

        # Erstelle neuen OptimizationRun
        optimization_run = OptimizationRun.objects.create(
            event=event,
            status='running',
            algorithm='mip_pulp',  # Mixed-Integer Programming mit PuLP
            started_at=timezone.now(),
            log_data={
                'initiated_by': request.user.username,
                'initiated_at': timezone.now().isoformat(),
                'max_distance_km': float(event.max_distance_km),
                'groups_per_course': event.groups_per_course,
                'team_size': event.team_size,
                'old_assignments_deleted': old_assignments_count,
                'algorithm': 'Mixed-Integer Programming (MIP)',
                'solver': 'PuLP CBC'
            }
        )

        # STARTE MIP-OPTIMIERUNG
        logger.info("🚀 Starte professionelle MIP-Optimierung...")
        solution = optimizer.optimize()

        team_count = len(solution['assignments'])
        total_distance = sum([assignment['total_distance']
                             for assignment in solution['assignments']])

        # Konvertiere MIP-Lösung zu Django-Modellen
        for assignment_data in solution['assignments']:
            team = assignment_data['team']
            hosts = assignment_data['hosts']
            course_hosted = assignment_data['course_hosted']
            distances = assignment_data['distances']

            # Erstelle TeamAssignment
            assignment = TeamAssignment.objects.create(
                optimization_run=optimization_run,
                team=team,
                course=course_hosted or 'guest',  # Kurs den das Team hostet
                hosts_appetizer=hosts.get('appetizer'),
                hosts_main_course=hosts.get('main_course'),
                hosts_dessert=hosts.get('dessert'),
                distance_to_appetizer=distances.get('appetizer', 0),
                distance_to_main_course=distances.get('main_course', 0),
                distance_to_dessert=distances.get('dessert', 0),
                total_distance=assignment_data['total_distance'],
                # Bessere Scores für kürzere Wege
                preference_score=round(
                    95.0 - (assignment_data['total_distance'] * 2), 1)
            )

            # Füge Gäste hinzu (wenn das Team hostet)
            if course_hosted:
                # Finde alle Teams die zu diesem Host kommen (korrekte Logik)
                guest_teams = []
                for other_assignment_data in solution['assignments']:
                    other_team = other_assignment_data['team']
                    other_hosts = other_assignment_data['hosts']

                    # Wenn das andere Team zu mir als Host für meinen Kurs kommt
                    if other_hosts.get(course_hosted) == team and other_team != team:
                        guest_teams.append(other_team)

                if guest_teams:
                    assignment.guests.set(guest_teams)
                    logger.info(
                        f"🏠 Team '{team.name}' hostet {course_hosted} für {len(guest_teams)} Gäste")

        # Optimierung abschließen
        optimization_run.status = 'completed'
        optimization_run.completed_at = timezone.now()
        optimization_run.total_distance = round(total_distance, 1)
        optimization_run.objective_value = round(
            solution['objective_value'], 1)
        optimization_run.iterations_completed = 1  # MIP ist exakt, keine Iterationen
        optimization_run.execution_time = round(
            (timezone.now() - optimization_run.started_at).total_seconds(), 1)
        optimization_run.log_data.update({
            'optimization_completed': True,
            'routes_created': team_count,
            'avg_distance_per_team': round(total_distance / team_count, 2),
            'mip_objective_value': solution['objective_value'],
            'penalties': solution['penalties'],
            'travel_times': solution['travel_times'],
            'hosting_distribution': solution['hosting']
        })
        optimization_run.save()

        # Setze Event-Status auf "Optimiert"
        event.status = 'optimized'
        event.save()

        messages.success(
            request,
            f'Optimierung erfolgreich abgeschlossen! {team_count} Teams optimiert mit '
            f'{optimization_run.algorithm}. Die Ergebnisse können nun an die Teams gesendet werden.'
        )

    except Exception as e:
        event.status = 'registration_closed'
        event.save()
        messages.error(
            request, f'Fehler bei der Optimierung: {str(e)}')

    return redirect('events:manage_event', event_id=event_id)


@login_required
def optimization_results(request, event_id):
    """Optimierungsergebnisse anzeigen und bearbeiten"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung - nur für Staff-User oder Event-Organisatoren
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(
            request, 'Sie haben keine Berechtigung, die Optimierungsergebnisse zu sehen.')
        return redirect('events:event_detail', event_id=event_id)

    # Hole die neueste Optimierung
    from optimization.models import OptimizationRun, TeamAssignment
    latest_optimization = event.optimization_runs.filter(
        status='completed'
    ).order_by('-completed_at').first()

    if not latest_optimization:
        messages.warning(
            request, 'Noch keine Optimierung durchgeführt.')
        return redirect('events:manage_event', event_id=event_id)

    # Hole alle Team-Zuweisungen
    assignments = TeamAssignment.objects.filter(
        optimization_run=latest_optimization
    ).select_related('team', 'hosts_appetizer', 'hosts_main_course', 'hosts_dessert').prefetch_related('guests')

    # Gruppiere nach Kursen für bessere Übersicht
    assignments_by_course = {
        'appetizer': assignments.filter(course='appetizer'),
        'main_course': assignments.filter(course='main_course'),
        'dessert': assignments.filter(course='dessert'),
    }

    # Erstelle Host-Übersicht
    hosting_overview = {}
    for assignment in assignments:
        if assignment.course == 'appetizer' and assignment.hosts_appetizer is None:
            # Das Team hostet Vorspeise
            hosting_overview.setdefault('appetizer', []).append({
                'host': assignment.team,
                'guests': list(assignment.guests.all())
            })
        elif assignment.course == 'main_course' and assignment.hosts_main_course is None:
            # Das Team hostet Hauptgang
            hosting_overview.setdefault('main_course', []).append({
                'host': assignment.team,
                'guests': list(assignment.guests.all())
            })
        elif assignment.course == 'dessert' and assignment.hosts_dessert is None:
            # Das Team hostet Nachspeise
            hosting_overview.setdefault('dessert', []).append({
                'host': assignment.team,
                'guests': list(assignment.guests.all())
            })

    # Berechne Statistiken
    total_distance = sum(a.total_distance or 0 for a in assignments)
    avg_distance = total_distance / len(assignments) if assignments else 0
    avg_preference_score = sum(
        a.preference_score or 0 for a in assignments) / len(assignments) if assignments else 0

    context = {
        'event': event,
        'optimization_run': latest_optimization,
        'assignments': assignments,
        'assignments_by_course': assignments_by_course,
        'hosting_overview': hosting_overview,
        'stats': {
            'total_teams': len(assignments),
            'total_distance': round(total_distance, 1),
            'avg_distance': round(avg_distance, 1),
            'avg_preference_score': round(avg_preference_score, 1),
        }
    }

    return render(request, 'events/optimization_results.html', context)


@login_required
@require_http_methods(["POST"])
def send_team_emails(request, event_id):
    """E-Mails an alle Teams senden"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.can_user_manage_event(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, E-Mails zu senden.')
        return redirect('events:optimization_results', event_id=event_id)

    # TODO: Hier würde der echte E-Mail-Versand implementiert
    from optimization.models import OptimizationRun, TeamAssignment
    latest_optimization = event.optimization_runs.filter(
        status='completed'
    ).order_by('-completed_at').first()

    if not latest_optimization:
        messages.error(request, 'Keine Optimierung gefunden.')
        return redirect('events:manage_event', event_id=event_id)

    assignments = TeamAssignment.objects.filter(
        optimization_run=latest_optimization
    ).select_related('team')

    # Placeholder: Simuliere E-Mail-Versand
    email_count = 0
    for assignment in assignments:
        # TODO: Hier würde die echte E-Mail gesendet
        # send_team_assignment_email(assignment)
        email_count += 1

    messages.success(
        request,
        f'E-Mails erfolgreich an {email_count} Teams gesendet! '
        '(Hinweis: Dies ist aktuell nur eine Simulation)'
    )

    return redirect('events:optimization_results', event_id=event_id)


@login_required
@require_http_methods(["POST"])
def adjust_assignment(request, event_id, assignment_id):
    """Manuelle Anpassung einer Team-Zuweisung"""
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.can_user_manage_event(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, Zuweisungen zu ändern.')
        return redirect('events:optimization_results', event_id=event_id)

    from optimization.models import TeamAssignment
    from accounts.models import Team

    assignment = get_object_or_404(
        TeamAssignment, id=assignment_id, optimization_run__event=event)

    try:
        # Update assignment data
        assignment.course = request.POST.get('course')

        # Update host assignments
        hosts_appetizer_id = request.POST.get('hosts_appetizer')
        hosts_main_course_id = request.POST.get('hosts_main_course')
        hosts_dessert_id = request.POST.get('hosts_dessert')

        assignment.hosts_appetizer = Team.objects.get(
            id=hosts_appetizer_id) if hosts_appetizer_id else None
        assignment.hosts_main_course = Team.objects.get(
            id=hosts_main_course_id) if hosts_main_course_id else None
        assignment.hosts_dessert = Team.objects.get(
            id=hosts_dessert_id) if hosts_dessert_id else None

        # TODO: Recalculate distances based on new assignments
        # For now, keep existing distances

        assignment.save()

        messages.success(
            request,
            f'Zuweisung für Team "{assignment.team.name}" erfolgreich angepasst!'
        )

    except Exception as e:
        messages.error(
            request, f'Fehler beim Anpassen der Zuweisung: {str(e)}')

    return redirect('events:optimization_results', event_id=event_id)


@login_required
def get_route_geometry(request, event_id):
    """
    API-Endpoint für Route-Geometrie (echte Fußwege für Kartendarstellung)
    """
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    # Parameter aus Request
    start_lat = request.GET.get('start_lat')
    start_lng = request.GET.get('start_lng')
    end_lat = request.GET.get('end_lat')
    end_lng = request.GET.get('end_lng')

    if not all([start_lat, start_lng, end_lat, end_lng]):
        return JsonResponse({'error': 'Fehlende Koordinaten'}, status=400)

    try:
        start_coords = (float(start_lat), float(start_lng))
        end_coords = (float(end_lat), float(end_lng))

        # Hole Route-Geometrie
        from .routing import get_route_calculator
        route_calc = get_route_calculator()

        route_points = route_calc.get_walking_route_geometry(
            start_coords, end_coords)

        return JsonResponse({
            'success': True,
            'route_points': route_points,
            'point_count': len(route_points) if route_points else 0
        })

    except ValueError:
        return JsonResponse({'error': 'Ungültige Koordinaten'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Route-Fehler: {str(e)}'}, status=500)


@login_required
def get_optimization_progress(request, event_id):
    """
    API-Endpoint für Optimierung-Progress Updates
    """
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not (request.user.is_staff or request.user.is_superuser):
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    from django.core.cache import cache

    progress_key = f"optimization_progress_{event_id}"
    log_key = f"optimization_log_{event_id}"

    progress = cache.get(progress_key, {
        'step': 0,
        'total_steps': 5,
        'current_task': 'Keine aktive Optimierung',
        'percentage': 0,
        'status': 'idle'
    })

    logs = cache.get(log_key, [])

    return JsonResponse({
        'success': True,
        'progress': progress,
        'logs': logs[-20:]  # Nur die letzten 20 Log-Einträge
    })


@login_required
@require_http_methods(["POST"])
def run_additional_optimization(request, event_id):
    """
    Führe weitere Optimierungsiterationen durch
    """
    event = get_object_or_404(Event, id=event_id)

    # Prüfe Berechtigung
    if not event.can_user_run_optimization(request.user):
        messages.error(
            request, 'Sie haben keine Berechtigung, weitere Optimierungen zu starten.')
        return redirect('events:optimization_results', event_id=event_id)

    try:
        from events.optimization import RunningDinnerOptimizer

        # Hole Anzahl zusätzlicher Iterationen aus Form
        additional_iterations = int(
            request.POST.get('additional_iterations', 5))
        additional_iterations = max(
            1, min(additional_iterations, 10))  # 1-10 Iterationen

        messages.info(
            request, f'🔄 Starte {additional_iterations} weitere Optimierungsiterationen...')

        # Führe zusätzliche Optimierung durch
        optimizer = RunningDinnerOptimizer(event)
        solution = optimizer.run_additional_optimization(
            max_additional_iterations=additional_iterations)

        messages.success(
            request,
            f'✅ Weitere Optimierung abgeschlossen! '
            f'Neue Gesamtdistanz: {solution["objective_value"]:.1f}km'
        )

    except Exception as e:
        logger.error(f"Weitere Optimierung fehlgeschlagen: {e}")
        messages.error(
            request, f'❌ Weitere Optimierung fehlgeschlagen: {str(e)}')

    return redirect('events:optimization_results', event_id=event_id)
