from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count

from .models import CustomUser, Team, TeamMembership, TeamInvitation, DietaryRestriction


@admin.register(DietaryRestriction)
class DietaryRestrictionAdmin(admin.ModelAdmin):
    """Admin für Ernährungseinschränkungen"""
    
    list_display = ['name', 'category', 'severity', 'is_active', 'is_critical_display', 'user_count']
    list_filter = ['category', 'severity', 'is_active']
    search_fields = ['name', 'description', 'common_ingredients']
    ordering = ['category', 'severity', 'name']
    
    fieldsets = (
        (_('Grunddaten'), {
            'fields': ('name', 'category', 'severity', 'is_active')
        }),
        (_('Beschreibung'), {
            'fields': ('description', 'common_ingredients', 'alternatives')
        }),
        (_('Notfall-Information'), {
            'fields': ('emergency_info',),
            'classes': ('collapse',)
        }),
    )
    
    def is_critical_display(self, obj):
        """Zeige kritische Allergien hervorgehoben"""
        if obj.is_critical:
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Kritisch</span>')
        return format_html('<span style="color: green;">✓ Normal</span>')
    is_critical_display.short_description = _('Schweregrad')
    
    def user_count(self, obj):
        """Anzahl User mit dieser Einschränkung"""
        count = obj.customuser_set.count()
        return f"{count} User"
    user_count.short_description = _('Betroffene User')


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin mit erweiterten Feldern"""
    
    list_display = (
        'email', 'username', 'first_name', 'last_name', 
        'is_verified', 'is_staff', 'date_joined', 'team_count', 'dietary_status'
    )
    list_filter = (
        'is_staff', 'is_superuser', 'is_active', 'is_verified',
        'privacy_accepted', 'newsletter_consent', 'date_joined',
        'dietary_restrictions_structured'
    )
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Persönliche Informationen'), {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 
                      'date_of_birth', 'profile_picture')
        }),
        (_('Ernährung & Notfall'), {
            'fields': ('dietary_restrictions_structured', 'dietary_restrictions', 'emergency_contact', 'emergency_phone'),
            'classes': ('collapse',)
        }),
        (_('Berechtigungen'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        (_('Datenschutz & Einstellungen'), {
            'fields': ('is_verified', 'privacy_accepted', 'newsletter_consent'),
            'classes': ('collapse',)
        }),
        (_('Wichtige Daten'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('last_login', 'date_joined')
    filter_horizontal = ('dietary_restrictions_structured',)
    
    def team_count(self, obj):
        """Anzahl Teams des Users"""
        return obj.team_memberships.filter(is_active=True).count()
    team_count.short_description = _('Teams')
    
    def dietary_status(self, obj):
        """Zeige Ernährungsstatus an"""
        if obj.critical_allergies.exists():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ Kritische Allergien</span>')
        elif obj.has_dietary_restrictions:
            return format_html('<span style="color: orange;">📋 Einschränkungen</span>')
        else:
            return format_html('<span style="color: green;">✓ Keine</span>')
    dietary_status.short_description = _('Ernährung')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('team_memberships')


class TeamMembershipInline(admin.TabularInline):
    """Inline für Team-Mitgliedschaften"""
    model = TeamMembership
    extra = 0
    fields = ('user', 'role', 'is_active', 'joined_at')
    readonly_fields = ('joined_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Team Admin mit umfassender Verwaltung"""
    
    list_display = (
        'name', 'contact_person', 'member_count_display', 'home_address_short',
        'has_kitchen_display', 'participation_type_display', 'max_guests', 
        'team_allergies_display', 'is_active', 'created_at'
    )
    list_filter = ('is_active', 'has_kitchen', 'participation_type', 'max_members', 'created_at')
    search_fields = ('name', 'description', 'contact_person__email', 'home_address')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Grundinformationen'), {
            'fields': ('name', 'description', 'contact_person', 'is_active')
        }),
        (_('Team-Konfiguration'), {
            'fields': ('max_members', 'max_guests', 'has_kitchen', 'participation_type')
        }),
        (_('Adresse & Standort'), {
            'fields': ('home_address', 'latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        (_('Koch-Informationen'), {
            'fields': ('cooking_preferences', 'kitchen_equipment', 'accessibility_notes'),
            'classes': ('collapse',)
        }),
        (_('Metadaten'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TeamMembershipInline]
    
    def member_count_display(self, obj):
        """Zeige Mitgliederzahl mit Farbe"""
        count = obj.member_count
        max_count = obj.max_members
        
        if count == max_count:
            color = 'green'
        elif count < max_count:
            color = 'orange'
        else:
            color = 'red'
            
        return format_html(
            '<span style="color: {};">{}/{}</span>',
            color, count, max_count
        )
    member_count_display.short_description = _('Mitglieder')
    
    def home_address_short(self, obj):
        """Kurze Adresse"""
        if len(obj.home_address) > 50:
            return obj.home_address[:47] + '...'
        return obj.home_address
    home_address_short.short_description = _('Adresse')
    
    def team_allergies_display(self, obj):
        """Zeige Team-Allergiestatus"""
        critical = obj.critical_team_allergies
        all_restrictions = obj.team_dietary_restrictions
        
        if critical.exists():
            return format_html('<span style="color: red; font-weight: bold;">⚠️ {} kritisch</span>', critical.count())
        elif all_restrictions.exists():
            return format_html('<span style="color: orange;">📋 {} Einschränkungen</span>', all_restrictions.count())
        else:
            return format_html('<span style="color: green;">✓ Keine</span>')
    team_allergies_display.short_description = _('Team-Allergien')
    
    def has_kitchen_display(self, obj):
        """Zeigt Küchen-Status mit Icon"""
        if obj.has_kitchen:
            return format_html('<span style="color: green; font-weight: bold;">🏠 Ja</span>')
        else:
            return format_html('<span style="color: red; font-weight: bold;">❌ Nein</span>')
    has_kitchen_display.short_description = _('Küche')
    
    def participation_type_display(self, obj):
        """Zeigt Teilnahme-Art mit Farbe"""
        colors = {
            'full': 'green',
            'kitchen_only': 'blue', 
            'guest_only': 'orange'
        }
        icons = {
            'full': '👥',
            'kitchen_only': '🏠',
            'guest_only': '🍽️'
        }
        color = colors.get(obj.participation_type, 'black')
        icon = icons.get(obj.participation_type, '❓')
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_participation_type_display()
        )
    participation_type_display.short_description = _('Teilnahme-Art')
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('contact_person').prefetch_related('members')


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    """Team-Mitgliedschaft Admin"""
    
    list_display = ('user', 'team', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active', 'joined_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'team__name')
    ordering = ('-joined_at',)
    
    fieldsets = (
        (_('Mitgliedschaft'), {
            'fields': ('user', 'team', 'role', 'is_active')
        }),
        (_('Metadaten'), {
            'fields': ('joined_at',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('joined_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'team')


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    """Team-Einladungen Admin"""
    
    list_display = (
        'email', 'team', 'invited_by', 'status', 'created_at', 'expires_at', 'is_expired_display'
    )
    list_filter = ('status', 'created_at', 'expires_at')
    search_fields = ('email', 'team__name', 'invited_by__email')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Einladung'), {
            'fields': ('team', 'invited_by', 'email', 'message')
        }),
        (_('Status'), {
            'fields': ('status', 'token')
        }),
        (_('Zeitdaten'), {
            'fields': ('created_at', 'expires_at', 'responded_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'responded_at', 'token')
    
    def is_expired_display(self, obj):
        """Zeige Ablaufstatus mit Farbe"""
        if obj.is_expired:
            return format_html('<span style="color: red;">Abgelaufen</span>')
        else:
            return format_html('<span style="color: green;">Gültig</span>')
    is_expired_display.short_description = _('Status')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'invited_by')


# Admin Dashboard Anpassungen
admin.site.site_header = _('Running Dinner Administration')
admin.site.site_title = _('Running Dinner Admin')
admin.site.index_title = _('Willkommen in der Running Dinner Verwaltung')