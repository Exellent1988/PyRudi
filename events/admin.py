from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.utils import timezone

from .models import Event, Course, TeamRegistration, EventOrganizer


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin für Kurse"""

    list_display = ('display_name', 'name', 'order')
    list_editable = ('order',)
    ordering = ('order',)

    fieldsets = (
        (_('Kurs-Informationen'), {
            'fields': ('name', 'display_name', 'order')
        }),
    )


class TeamRegistrationInline(admin.TabularInline):
    """Inline für Team-Anmeldungen"""
    model = TeamRegistration
    extra = 0
    fields = ('team', 'status', 'preferred_course',
              'payment_status', 'registered_at')
    readonly_fields = ('registered_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team')


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Event Admin mit umfassender Verwaltung"""

    list_display = (
        'name', 'event_date', 'status_display', 'registered_teams_display',
        'organizer', 'is_public', 'created_at'
    )
    list_filter = (
        'status', 'is_public', 'event_date', 'created_at', 'city'
    )
    search_fields = ('name', 'description', 'organizer__email', 'city')
    ordering = ('-event_date',)

    fieldsets = (
        (_('Grundinformationen'), {
            'fields': ('name', 'description', 'organizer', 'status', 'is_public')
        }),
        (_('Zeitplan'), {
            'fields': (
                'event_date', 'registration_start', 'registration_deadline',
                'appetizer_time', 'main_course_time', 'dessert_time'
            )
        }),
        (_('Event-Konfiguration'), {
            'fields': ('max_teams', 'team_size', 'groups_per_course', 'price_per_person')
        }),
        (_('Standort'), {
            'fields': ('city', 'max_distance_km'),
            'classes': ('collapse',)
        }),

        (_('Metadaten'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('created_at', 'updated_at')
    inlines = [TeamRegistrationInline]

    actions = ['open_registration', 'close_registration', 'start_optimization']

    def status_display(self, obj):
        """Status mit Farbe anzeigen"""
        status_colors = {
            'planning': 'blue',
            'registration_open': 'green',
            'registration_closed': 'orange',
            'optimization_running': 'purple',
            'optimized': 'darkgreen',
            'in_progress': 'red',
            'completed': 'gray',
            'cancelled': 'darkred',
        }

        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = _('Status')

    def registered_teams_display(self, obj):
        """Angemeldete Teams mit Fortschrittsbalken"""
        registered = obj.registered_teams_count
        max_teams = obj.max_teams
        percentage = (registered / max_teams * 100) if max_teams > 0 else 0

        color = 'green' if percentage >= 80 else 'orange' if percentage >= 50 else 'red'

        return format_html(
            '<div style="width: 100px; background-color: #f0f0f0; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; height: 20px; border-radius: 3px; text-align: center; line-height: 20px; color: white; font-size: 12px;">'
            '{}/{}'
            '</div></div>',
            percentage, color, registered, max_teams
        )
    registered_teams_display.short_description = _('Anmeldungen')

    def open_registration(self, request, queryset):
        """Action: Anmeldung öffnen"""
        updated = queryset.filter(
            status__in=['planning', 'registration_closed']
        ).update(status='registration_open')

        self.message_user(
            request,
            f'{updated} Event(s) für Anmeldungen geöffnet.'
        )
    open_registration.short_description = _('Anmeldung öffnen')

    def close_registration(self, request, queryset):
        """Action: Anmeldung schließen"""
        updated = queryset.filter(
            status='registration_open'
        ).update(status='registration_closed')

        self.message_user(
            request,
            f'{updated} Event(s) für Anmeldungen geschlossen.'
        )
    close_registration.short_description = _('Anmeldung schließen')

    def start_optimization(self, request, queryset):
        """Action: Optimierung starten"""
        for event in queryset.filter(status='registration_closed'):
            if event.can_be_optimized:
                event.status = 'optimization_running'
                event.save()
                # Hier würde die Optimierung gestartet werden
                self.message_user(
                    request,
                    f'Optimierung für "{event.name}" gestartet.'
                )
            else:
                self.message_user(
                    request,
                    f'Event "{event.name}" kann nicht optimiert werden (zu wenige Teams).',
                    level='warning'
                )
    start_optimization.short_description = _('Optimierung starten')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('organizer').annotate(
            registered_teams_count=Count(
                'team_registrations',
                filter=Q(team_registrations__status='confirmed')
            )
        )


@admin.register(TeamRegistration)
class TeamRegistrationAdmin(admin.ModelAdmin):
    """Team-Anmeldungen Admin"""

    list_display = (
        'team', 'event', 'status_display', 'preferred_course',
        'payment_status_display', 'registered_at'
    )
    list_filter = (
        'status', 'payment_status', 'preferred_course',
        'can_host_appetizer', 'can_host_main_course', 'can_host_dessert',
        'registered_at'
    )
    search_fields = (
        'team__name', 'event__name', 'team__contact_person__email'
    )
    ordering = ('-registered_at',)

    fieldsets = (
        (_('Anmeldung'), {
            'fields': ('event', 'team', 'status')
        }),
        (_('Hosting-Präferenzen'), {
            'fields': (
                'preferred_course', 'can_host_appetizer',
                'can_host_main_course', 'can_host_dessert'
            )
        }),
        (_('Zahlung'), {
            'fields': ('payment_status',),
            'classes': ('collapse',)
        }),
        (_('Metadaten'), {
            'fields': ('registered_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('registered_at', 'updated_at')

    actions = ['confirm_registration', 'move_to_waiting_list', 'mark_as_paid']

    def status_display(self, obj):
        """Status mit Farbe"""
        status_colors = {
            'pending': 'orange',
            'confirmed': 'green',
            'waiting_list': 'blue',
            'cancelled': 'red',
            'rejected': 'darkred',
        }

        color = status_colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = _('Status')

    def payment_status_display(self, obj):
        """Zahlungsstatus mit Farbe"""
        payment_colors = {
            'pending': 'orange',
            'paid': 'green',
            'refunded': 'red',
        }

        color = payment_colors.get(obj.payment_status, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color, obj.get_payment_status_display()
        )
    payment_status_display.short_description = _('Zahlung')

    def confirm_registration(self, request, queryset):
        """Action: Anmeldung bestätigen"""
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(
            request,
            f'{updated} Anmeldung(en) bestätigt.'
        )
    confirm_registration.short_description = _('Anmeldung bestätigen')

    def move_to_waiting_list(self, request, queryset):
        """Action: Auf Warteliste setzen"""
        updated = queryset.exclude(
            status='waiting_list').update(status='waiting_list')
        self.message_user(
            request,
            f'{updated} Team(s) auf Warteliste gesetzt.'
        )
    move_to_waiting_list.short_description = _('Auf Warteliste setzen')

    def mark_as_paid(self, request, queryset):
        """Action: Als bezahlt markieren"""
        updated = queryset.filter(
            payment_status='pending').update(payment_status='paid')
        self.message_user(
            request,
            f'{updated} Zahlung(en) als bezahlt markiert.'
        )
    mark_as_paid.short_description = _('Als bezahlt markieren')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'event')


@admin.register(EventOrganizer)
class EventOrganizerAdmin(admin.ModelAdmin):
    """Admin für Event-Organisatoren"""

    list_display = (
        'user', 'event', 'role', 'invited_by', 'invited_at', 'is_active', 'permissions_display'
    )
    list_filter = ('role', 'is_active', 'invited_at')
    search_fields = ('user__email', 'user__first_name',
                     'user__last_name', 'event__name')
    ordering = ('-invited_at',)

    fieldsets = (
        (_('Organisator'), {
            'fields': ('event', 'user', 'role', 'is_active')
        }),
        (_('Berechtigungen'), {
            'fields': ('permissions',)
        }),
        (_('Einladung'), {
            'fields': ('invited_by', 'invited_at'),
            'classes': ('collapse',)
        }),
        (_('Notizen'), {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ('invited_at',)

    def permissions_display(self, obj):
        """Zeigt Berechtigungen als lesbare Liste"""
        if obj.permissions:
            perm_display = obj.get_permission_display_list()
            if len(perm_display) > 2:
                return f"{', '.join(perm_display[:2])} +{len(perm_display)-2} weitere"
            return ', '.join(perm_display)
        return _('Keine besonderen Berechtigungen')
    permissions_display.short_description = _('Berechtigungen')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'event', 'invited_by')


# Dashboard anpassungen
