from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal


class Event(models.Model):
    """Hauptmodell für Running Dinner Events"""

    STATUS_CHOICES = [
        ('planning', _('Planung')),
        ('registration_open', _('Anmeldung geöffnet')),
        ('registration_closed', _('Anmeldung geschlossen')),
        ('optimization_running', _('Optimierung läuft')),
        ('optimized', _('Optimiert')),
        ('in_progress', _('Läuft')),
        ('completed', _('Abgeschlossen')),
        ('cancelled', _('Abgesagt')),
    ]

    name = models.CharField(
        _('Event-Name'),
        max_length=200
    )
    description = models.TextField(
        _('Beschreibung'),
        help_text=_('Detaillierte Beschreibung des Events')
    )
    # Haupt-Organisator (Rückwärtskompatibilität)
    organizer = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        related_name='organized_events',
        verbose_name=_('Haupt-Organisator')
    )

    # Zusätzliche Organisatoren
    organizers = models.ManyToManyField(
        'accounts.CustomUser',
        through='EventOrganizer',
        through_fields=('event', 'user'),
        related_name='co_organized_events',
        verbose_name=_('Alle Organisatoren'),
        blank=True
    )

    # Event-Zeiten
    event_date = models.DateField(
        _('Event-Datum')
    )
    registration_start = models.DateTimeField(
        _('Anmeldung startet')
    )
    registration_deadline = models.DateTimeField(
        _('Anmeldeschluss')
    )

    # Kurs-Zeiten
    appetizer_time = models.TimeField(
        _('Vorspeise Zeit'),
        default='18:00'
    )
    main_course_time = models.TimeField(
        _('Hauptgang Zeit'),
        default='20:00'
    )
    dessert_time = models.TimeField(
        _('Nachspeise Zeit'),
        default='22:00'
    )

    # Event-Konfiguration
    max_teams = models.PositiveIntegerField(
        _('Maximale Team-Anzahl'),
        validators=[MinValueValidator(3)],
        help_text=_('Mindestens 3 Teams erforderlich')
    )
    team_size = models.PositiveIntegerField(
        _('Team-Größe'),
        default=2,
        validators=[MinValueValidator(1), MaxValueValidator(6)]
    )
    groups_per_course = models.PositiveIntegerField(
        _('Teams pro Kurs'),
        default=3,
        validators=[MinValueValidator(2), MaxValueValidator(6)],
        help_text=_('Anzahl Teams die zusammen an einem Kurs teilnehmen')
    )

    # Kosten
    price_per_person = models.DecimalField(
        _('Preis pro Person'),
        max_digits=6,
        decimal_places=2,
        default=Decimal('25.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    # Standort-Einstellungen
    city = models.CharField(
        _('Stadt'),
        max_length=100
    )
    max_distance_km = models.DecimalField(
        _('Maximale Entfernung (km)'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text=_('Maximale Entfernung zwischen Kursen')
    )

    # Status und Metadaten
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='planning'
    )
    is_public = models.BooleanField(
        _('Öffentlich'),
        default=True,
        help_text=_('Soll das Event öffentlich sichtbar sein?')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Event')
        verbose_name_plural = _('Events')
        ordering = ['-event_date']

    def __str__(self):
        return f"{self.name} - {self.event_date}"

    @property
    def is_registration_open(self):
        now = timezone.now()
        return (self.registration_start <= now <= self.registration_deadline and
                self.status == 'registration_open')

    def get_all_organizers(self):
        """Gibt alle Organisatoren (Haupt + Co-Organisatoren) zurück"""
        organizer_ids = [self.organizer.id]
        co_organizer_ids = list(self.organizers.values_list('id', flat=True))
        all_ids = list(set(organizer_ids + co_organizer_ids))

        from accounts.models import CustomUser
        return CustomUser.objects.filter(id__in=all_ids)

    def can_user_manage_event(self, user):
        """Prüft ob ein User das Event verwalten kann"""
        if user == self.organizer:
            return True

        try:
            organizer_role = EventOrganizer.objects.get(
                event=self, user=user, is_active=True)
            return organizer_role.can_manage_event
        except EventOrganizer.DoesNotExist:
            return False

    def can_user_manage_teams(self, user):
        """Prüft ob ein User Teams verwalten kann"""
        if user == self.organizer:
            return True

        try:
            organizer_role = EventOrganizer.objects.get(
                event=self, user=user, is_active=True)
            return organizer_role.can_manage_teams
        except EventOrganizer.DoesNotExist:
            return False

    def can_user_run_optimization(self, user):
        """Prüft ob ein User die Optimierung starten kann"""
        if user == self.organizer:
            return True

        try:
            organizer_role = EventOrganizer.objects.get(
                event=self, user=user, is_active=True)
            return organizer_role.can_run_optimization
        except EventOrganizer.DoesNotExist:
            return False

    def get_organizer_role(self, user):
        """Gibt die Rolle eines Users für dieses Event zurück"""
        if user == self.organizer:
            return 'main_organizer'

        try:
            organizer_role = EventOrganizer.objects.get(
                event=self, user=user, is_active=True)
            return organizer_role.role
        except EventOrganizer.DoesNotExist:
            return None

    @property
    def organizer_count(self):
        """Gibt die Anzahl aller Organisatoren zurück"""
        return 1 + self.organizers.filter(eventorganizer__is_active=True).count()

    @property
    def team_count(self):
        """Gibt die Anzahl angemeldeter Teams zurück"""
        return self.team_registrations.filter(status__in=['confirmed', 'pending']).count()


class Course(models.Model):
    """Modell für die verschiedenen Kurse (Vorspeise, Hauptgang, Nachspeise)"""

    COURSE_CHOICES = [
        ('appetizer', _('Vorspeise')),
        ('main_course', _('Hauptgang')),
        ('dessert', _('Nachspeise')),
    ]

    name = models.CharField(
        _('Kurs-Name'),
        max_length=20,
        choices=COURSE_CHOICES
    )
    display_name = models.CharField(
        _('Anzeigename'),
        max_length=50
    )
    order = models.PositiveIntegerField(
        _('Reihenfolge'),
        unique=True
    )

    class Meta:
        verbose_name = _('Kurs')
        verbose_name_plural = _('Kurse')
        ordering = ['order']

    def __str__(self):
        return self.display_name


class TeamRegistration(models.Model):
    """Modell für Team-Anmeldungen zu Events"""

    STATUS_CHOICES = [
        ('pending', _('Ausstehend')),
        ('confirmed', _('Bestätigt')),
        ('waiting_list', _('Warteliste')),
        ('cancelled', _('Storniert')),
        ('rejected', _('Abgelehnt')),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='team_registrations',
        verbose_name=_('Event')
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='event_registrations',
        verbose_name=_('Team')
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Hosting-Präferenzen
    preferred_course = models.CharField(
        _('Bevorzugter Kurs'),
        max_length=20,
        choices=Course.COURSE_CHOICES,
        null=True,
        blank=True,
        help_text=_('Welchen Kurs würde das Team gerne hosten?')
    )
    can_host_appetizer = models.BooleanField(
        _('Kann Vorspeise hosten'),
        default=True
    )
    can_host_main_course = models.BooleanField(
        _('Kann Hauptgang hosten'),
        default=True
    )
    can_host_dessert = models.BooleanField(
        _('Kann Nachspeise hosten'),
        default=True
    )

    # Zahlungsinformationen
    payment_status = models.CharField(
        _('Zahlungsstatus'),
        max_length=20,
        choices=[
            ('pending', _('Ausstehend')),
            ('paid', _('Bezahlt')),
            ('refunded', _('Erstattet')),
        ],
        default='pending'
    )

    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Team-Anmeldung')
        verbose_name_plural = _('Team-Anmeldungen')
        unique_together = ['event', 'team']
        ordering = ['registered_at']

    def __str__(self):
        return f"{self.team.name} - {self.event.name} ({self.get_status_display()})"


class EventOrganizer(models.Model):
    """Zwischen-Modell für Event-Organisatoren mit Rollen"""

    ROLE_CHOICES = [
        ('admin', _('Administrator')),
        ('moderator', _('Moderator')),
        ('assistant', _('Assistent')),
    ]

    PERMISSION_CHOICES = [
        ('manage_teams', _('Teams verwalten')),
        ('edit_event', _('Event bearbeiten')),
        ('run_optimization', _('Optimierung starten')),
        ('manage_organizers', _('Organisatoren verwalten')),
        ('view_analytics', _('Statistiken ansehen')),
        ('send_notifications', _('Benachrichtigungen senden')),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        verbose_name=_('Event')
    )
    user = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.CASCADE,
        verbose_name=_('Organisator')
    )
    role = models.CharField(
        _('Rolle'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='assistant'
    )
    permissions = models.JSONField(
        _('Berechtigungen'),
        default=list,
        help_text=_('Liste der Berechtigungen für diesen Organisator')
    )

    invited_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invited_organizers',
        verbose_name=_('Eingeladen von')
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(_('Aktiv'), default=True)

    notes = models.TextField(
        _('Notizen'),
        blank=True,
        help_text=_('Interne Notizen zu diesem Organisator')
    )

    class Meta:
        verbose_name = _('Event-Organisator')
        verbose_name_plural = _('Event-Organisatoren')
        unique_together = ['event', 'user']
        ordering = ['role', 'invited_at']

    def __str__(self):
        return f"{self.user.full_name} - {self.event.name} ({self.get_role_display()})"

    def has_permission(self, permission):
        """Prüft ob der Organisator eine bestimmte Berechtigung hat"""
        return permission in self.permissions

    def get_permission_display_list(self):
        """Gibt eine lesbare Liste der Berechtigungen zurück"""
        perm_dict = dict(self.PERMISSION_CHOICES)
        return [perm_dict.get(perm, perm) for perm in self.permissions]

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def can_manage_event(self):
        return self.role in ['admin', 'moderator'] or self.has_permission('edit_event')

    @property
    def can_manage_teams(self):
        return self.role in ['admin', 'moderator'] or self.has_permission('manage_teams')

    @property
    def can_run_optimization(self):
        return self.role in ['admin', 'moderator'] or self.has_permission('run_optimization')
