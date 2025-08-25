from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
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
        user_teams = Team.objects.filter(members=request.user, is_active=True)
        user_registrations = TeamRegistration.objects.filter(
            event=event,
            team__members=request.user
        )

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

    context = {
        'events': all_events,
        'stats': {
            'total_events': total_events,
            'active_events': active_events,
            'total_teams': total_teams,
        }
    }
    return render(request, 'events/organizer_dashboard.html', context)


@login_required
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

    context = {
        'event': event,
        'registrations': registrations,
        'organizers': organizers,
        'user_role': event.get_organizer_role(request.user),
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
