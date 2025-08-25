from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from .models import CustomUser, Team, TeamMembership, TeamInvitation
import json


# REST API ViewSets
class UserViewSet(viewsets.ModelViewSet):
    """API ViewSet für User-Management"""
    queryset = CustomUser.objects.all()
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Limitiere Queryset auf den aktuellen User oder Admin"""
        if self.request.user.is_staff:
            return CustomUser.objects.all()
        return CustomUser.objects.filter(id=self.request.user.id)

    @action(detail=False, methods=['get', 'patch'])
    def profile(self, request):
        """Profil des aktuellen Users abrufen/bearbeiten"""
        user = request.user
        if request.method == 'GET':
            return Response({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number,
                'dietary_restrictions': user.dietary_restrictions,
            })
        elif request.method == 'PATCH':
            # Hier würde normalerweise ein Serializer verwendet
            user.first_name = request.data.get('first_name', user.first_name)
            user.last_name = request.data.get('last_name', user.last_name)
            user.phone_number = request.data.get(
                'phone_number', user.phone_number)
            user.dietary_restrictions = request.data.get(
                'dietary_restrictions', user.dietary_restrictions)
            user.save()
            return Response({'message': 'Profil aktualisiert'})


class TeamViewSet(viewsets.ModelViewSet):
    """API ViewSet für Team-Management"""
    queryset = Team.objects.all()
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filtere Teams basierend auf User-Berechtigung"""
        user = self.request.user
        if user.is_staff:
            return Team.objects.all()
        return Team.objects.filter(members=user, is_active=True)

    def perform_create(self, serializer):
        """Erstelle Team und setze aktuellen User als Leader"""
        team_data = serializer.validated_data
        team = Team.objects.create(
            name=team_data['name'],
            description=team_data.get('description', ''),
            home_address=team_data['home_address'],
            contact_person=self.request.user
        )
        TeamMembership.objects.create(
            user=self.request.user,
            team=team,
            role='leader'
        )
        return team

    @action(detail=True, methods=['post'])
    def invite_member(self, request, pk=None):
        """Lade neues Mitglied zum Team ein"""
        team = self.get_object()
        email = request.data.get('email')
        message = request.data.get('message', '')

        # Prüfe ob User berechtigt ist Einladungen zu senden
        membership = TeamMembership.objects.filter(
            user=request.user, team=team, role__in=['leader', 'member']
        ).first()

        if not membership:
            return Response(
                {'error': 'Sie sind nicht berechtigt Einladungen für dieses Team zu senden.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Erstelle Einladung
        import uuid
        invitation = TeamInvitation.objects.create(
            team=team,
            invited_by=request.user,
            email=email,
            message=message,
            token=str(uuid.uuid4())
        )

        return Response({
            'message': 'Einladung versendet',
            'invitation_id': invitation.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Hole alle Mitglieder eines Teams"""
        team = self.get_object()
        memberships = TeamMembership.objects.filter(team=team, is_active=True)
        members_data = []
        for membership in memberships:
            members_data.append({
                'id': membership.user.id,
                'username': membership.user.username,
                'email': membership.user.email,
                'full_name': membership.user.full_name,
                'role': membership.role,
                'joined_at': membership.joined_at
            })
        return Response(members_data)


# Django Views
@login_required
def dashboard(request):
    """Dashboard für eingeloggte User"""
    user_teams = Team.objects.filter(members=request.user, is_active=True)
    team_invitations = TeamInvitation.objects.filter(
        email=request.user.email,
        status='pending'
    )

    context = {
        'user_teams': user_teams,
        'team_invitations': team_invitations,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def create_team(request):
    """Team erstellen"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        home_address = request.POST.get('home_address')
        max_guests = request.POST.get('max_guests', 6)

        try:
            team = Team.objects.create(
                name=name,
                description=description,
                home_address=home_address,
                max_guests=int(max_guests),
                contact_person=request.user
            )

            TeamMembership.objects.create(
                user=request.user,
                team=team,
                role='leader'
            )

            messages.success(
                request, f'Team "{name}" wurde erfolgreich erstellt!')
            return redirect('accounts:team_detail', team_id=team.id)

        except Exception as e:
            messages.error(
                request, f'Fehler beim Erstellen des Teams: {str(e)}')

    return render(request, 'accounts/create_team.html')


@login_required
def team_detail(request, team_id):
    """Team-Detail-Ansicht"""
    team = get_object_or_404(Team, id=team_id)

    # Prüfe ob User Mitglied des Teams ist
    membership = TeamMembership.objects.filter(
        user=request.user, team=team, is_active=True
    ).first()

    if not membership and not request.user.is_staff:
        messages.error(
            request, 'Sie haben keine Berechtigung dieses Team zu sehen.')
        return redirect('accounts:dashboard')

    team_members = TeamMembership.objects.filter(team=team, is_active=True)
    pending_invitations = TeamInvitation.objects.filter(
        team=team, status='pending')

    context = {
        'team': team,
        'membership': membership,
        'team_members': team_members,
        'pending_invitations': pending_invitations,
    }
    return render(request, 'accounts/team_detail.html', context)


@login_required
def edit_profile(request):
    """Profil bearbeiten mit Allergien"""
    if request.method == 'POST':
        try:
            # Basic fields
            request.user.first_name = request.POST.get('first_name', '')
            request.user.last_name = request.POST.get('last_name', '')
            request.user.phone_number = request.POST.get('phone_number', '')
            request.user.emergency_contact = request.POST.get(
                'emergency_contact', '')
            request.user.emergency_phone = request.POST.get(
                'emergency_phone', '')
            request.user.dietary_restrictions = request.POST.get(
                'dietary_restrictions', '')

            # Date of birth
            if request.POST.get('date_of_birth'):
                from datetime import datetime
                request.user.date_of_birth = datetime.strptime(
                    request.POST.get('date_of_birth'), '%Y-%m-%d'
                ).date()

            request.user.save()

            # Dietary restrictions (structured)
            selected_restrictions = request.POST.getlist(
                'dietary_restrictions_structured')
            request.user.dietary_restrictions_structured.set(
                selected_restrictions)

            messages.success(request, 'Profil erfolgreich aktualisiert!')
            return redirect('accounts:dashboard')

        except Exception as e:
            messages.error(request, f'Fehler beim Aktualisieren: {str(e)}')

    from .models import DietaryRestriction
    all_restrictions = DietaryRestriction.objects.filter(
        is_active=True).order_by('category', 'name')

    context = {
        'all_restrictions': all_restrictions,
        'user_restrictions': request.user.dietary_restrictions_structured.all(),
    }
    return render(request, 'accounts/edit_profile.html', context)
