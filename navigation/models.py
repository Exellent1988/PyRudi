from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Address(models.Model):
    """Modell für Adressen mit Geocoding"""

    street = models.CharField(_('Straße'), max_length=200)
    house_number = models.CharField(_('Hausnummer'), max_length=10)
    postal_code = models.CharField(_('Postleitzahl'), max_length=10)
    city = models.CharField(_('Stadt'), max_length=100)
    country = models.CharField(
        _('Land'), max_length=100, default='Deutschland')

    # Geocoding-Ergebnisse
    latitude = models.DecimalField(
        _('Breitengrad'), max_digits=10, decimal_places=8, null=True, blank=True
    )
    longitude = models.DecimalField(
        _('Längengrad'), max_digits=11, decimal_places=8, null=True, blank=True
    )
    geocoding_confidence = models.DecimalField(
        _('Geocoding-Konfidenz'), max_digits=3, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(
            Decimal('0.0')), MaxValueValidator(Decimal('1.0'))],
        help_text=_('Vertrauenswert des Geocoding-Ergebnisses (0.0-1.0)')
    )

    # Zusätzliche Informationen
    accessibility_notes = models.TextField(
        _('Barrierefreiheit'), blank=True, help_text=_('Informationen zur Barrierefreiheit')
    )
    parking_info = models.TextField(
        _('Parkmöglichkeiten'), blank=True, help_text=_('Informationen zu Parkmöglichkeiten')
    )
    public_transport_info = models.TextField(
        _('ÖPNV-Anbindung'), blank=True, help_text=_('Informationen zur öffentlichen Verkehrsanbindung')
    )

    # Metadaten
    is_verified = models.BooleanField(
        _('Verifiziert'), default=False, help_text=_('Wurde die Adresse manuell verifiziert?')
    )
    geocoded_at = models.DateTimeField(
        _('Geocodiert am'), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Adresse')
        verbose_name_plural = _('Adressen')
        ordering = ['city', 'street', 'house_number']

    def __str__(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}"

    @property
    def full_address(self):
        return f"{self.street} {self.house_number}, {self.postal_code} {self.city}, {self.country}"

    @property
    def has_coordinates(self):
        return self.latitude is not None and self.longitude is not None

    def get_coordinates(self):
        """Gibt Koordinaten als Tuple zurück"""
        if self.has_coordinates:
            return (float(self.latitude), float(self.longitude))
        return None


class Route(models.Model):
    """Modell für Routen zwischen zwei Punkten"""

    TRANSPORT_MODES = [
        ('walking', _('Zu Fuß')),
        ('cycling', _('Fahrrad')),
        ('driving', _('Auto')),
        ('public_transport', _('ÖPNV')),
    ]

    from_address = models.ForeignKey(
        Address, on_delete=models.CASCADE, related_name='routes_from', verbose_name=_('Von Adresse')
    )
    to_address = models.ForeignKey(
        Address, on_delete=models.CASCADE, related_name='routes_to', verbose_name=_('Zu Adresse')
    )
    transport_mode = models.CharField(
        _('Verkehrsmittel'), max_length=20, choices=TRANSPORT_MODES, default='driving'
    )

    # Routen-Daten
    distance_km = models.DecimalField(
        _('Entfernung (km)'), max_digits=8, decimal_places=3, null=True, blank=True
    )
    duration_minutes = models.PositiveIntegerField(
        _('Fahrtzeit (Minuten)'), null=True, blank=True)
    duration_with_traffic_minutes = models.PositiveIntegerField(
        _('Fahrtzeit mit Verkehr (Minuten)'), null=True, blank=True
    )

    # Routing-Details
    route_geometry = models.JSONField(
        _('Routen-Geometrie'), null=True, blank=True, help_text=_('GeoJSON-Geometrie der Route')
    )
    turn_by_turn_directions = models.JSONField(
        _('Turn-by-Turn Navigation'), null=True, blank=True, help_text=_('Detaillierte Navigationsanweisungen')
    )

    # API-Metadaten
    routing_service = models.CharField(
        _('Routing-Service'), max_length=50, blank=True, help_text=_('Verwendeter Routing-Service (z.B. OpenRouteService)')
    )
    last_updated = models.DateTimeField(
        _('Letzte Aktualisierung'), null=True, blank=True)
    is_cached = models.BooleanField(
        _('Gecacht'), default=True, help_text=_('Ist diese Route gecacht oder live berechnet?')
    )
    cache_expires_at = models.DateTimeField(
        _('Cache läuft ab'), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Route')
        verbose_name_plural = _('Routen')
        unique_together = ['from_address', 'to_address', 'transport_mode']
        ordering = ['distance_km']

    def __str__(self):
        mode_display = self.get_transport_mode_display()
        if self.distance_km and self.duration_minutes:
            return f"{self.from_address} → {self.to_address} ({mode_display}: {self.distance_km}km, {self.duration_minutes}min)"
        return f"{self.from_address} → {self.to_address} ({mode_display})"

    @property
    def is_cache_valid(self):
        """Prüft ob der Route-Cache noch gültig ist"""
        if not self.is_cached or not self.cache_expires_at:
            return False
        from django.utils import timezone
        return timezone.now() < self.cache_expires_at

    def get_average_speed_kmh(self):
        """Berechnet die Durchschnittsgeschwindigkeit"""
        if self.distance_km and self.duration_minutes and self.duration_minutes > 0:
            return float(self.distance_km) / (self.duration_minutes / 60.0)
        return None


class NavigationSession(models.Model):
    """Modell für Navigation-Sessions während eines Running Dinners"""

    STATUS_CHOICES = [
        ('preparing', _('Vorbereitung')),
        ('appetizer_travel', _('Unterwegs zur Vorspeise')),
        ('at_appetizer', _('Bei der Vorspeise')),
        ('main_course_travel', _('Unterwegs zum Hauptgang')),
        ('at_main_course', _('Beim Hauptgang')),
        ('dessert_travel', _('Unterwegs zur Nachspeise')),
        ('at_dessert', _('Bei der Nachspeise')),
        ('completed', _('Abgeschlossen')),
        ('cancelled', _('Abgebrochen')),
    ]

    team = models.ForeignKey(
        'accounts.Team', on_delete=models.CASCADE, related_name='navigation_sessions', verbose_name=_('Team')
    )
    event = models.ForeignKey(
        'events.Event', on_delete=models.CASCADE, related_name='navigation_sessions', verbose_name=_('Event')
    )
    optimization_run = models.ForeignKey(
        'optimization.OptimizationRun', on_delete=models.CASCADE, related_name='navigation_sessions', verbose_name=_('Optimierungslauf')
    )

    current_status = models.CharField(
        _('Aktueller Status'), max_length=20, choices=STATUS_CHOICES, default='preparing')
    current_location = models.ForeignKey(
        Address, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_sessions', verbose_name=_('Aktuelle Position')
    )

    # Zeitstempel
    started_at = models.DateTimeField(_('Gestartet um'), null=True, blank=True)
    appetizer_arrived_at = models.DateTimeField(
        _('Vorspeise erreicht um'), null=True, blank=True)
    main_course_arrived_at = models.DateTimeField(
        _('Hauptgang erreicht um'), null=True, blank=True)
    dessert_arrived_at = models.DateTimeField(
        _('Nachspeise erreicht um'), null=True, blank=True)
    completed_at = models.DateTimeField(
        _('Abgeschlossen um'), null=True, blank=True)

    # Navigation-Präferenzen
    preferred_transport_mode = models.CharField(
        _('Bevorzugtes Verkehrsmittel'), max_length=20, choices=Route.TRANSPORT_MODES, default='driving'
    )
    avoid_tolls = models.BooleanField(_('Maut vermeiden'), default=False)
    avoid_highways = models.BooleanField(
        _('Autobahn vermeiden'), default=False)

    # Notizen und Feedback
    notes = models.TextField(_('Notizen'), blank=True, help_text=_(
        'Notizen des Teams während der Navigation'))
    rating = models.PositiveIntegerField(
        _('Bewertung'), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Bewertung der Navigation (1-5 Sterne)')
    )
    feedback = models.TextField(
        _('Feedback'), blank=True, help_text=_('Feedback zur Navigation'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Navigation-Session')
        verbose_name_plural = _('Navigation-Sessions')
        unique_together = ['team', 'event']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.team.name} - {self.event.name} ({self.get_current_status_display()})"

    @property
    def is_active(self):
        return self.current_status not in ['completed', 'cancelled']

    def get_next_destination(self):
        """Gibt das nächste Ziel basierend auf dem aktuellen Status zurück"""
        from optimization.models import TeamAssignment
        try:
            assignment = TeamAssignment.objects.get(
                optimization_run=self.optimization_run, team=self.team)

            if self.current_status in ['preparing', 'appetizer_travel']:
                return assignment.hosts_appetizer
            elif self.current_status in ['at_appetizer', 'main_course_travel']:
                return assignment.hosts_main_course
            elif self.current_status in ['at_main_course', 'dessert_travel']:
                return assignment.hosts_dessert
        except TeamAssignment.DoesNotExist:
            pass
        return None


class LocationUpdate(models.Model):
    """Modell für GPS-Updates während der Navigation"""

    navigation_session = models.ForeignKey(
        NavigationSession, on_delete=models.CASCADE, related_name='location_updates', verbose_name=_('Navigation-Session')
    )

    latitude = models.DecimalField(
        _('Breitengrad'), max_digits=10, decimal_places=8)
    longitude = models.DecimalField(
        _('Längengrad'), max_digits=11, decimal_places=8)
    accuracy_meters = models.DecimalField(
        _('Genauigkeit (Meter)'), max_digits=8, decimal_places=2, null=True, blank=True)
    speed_kmh = models.DecimalField(
        _('Geschwindigkeit (km/h)'), max_digits=5, decimal_places=2, null=True, blank=True)
    bearing_degrees = models.DecimalField(
        _('Richtung (Grad)'), max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(
            Decimal('0.0')), MaxValueValidator(Decimal('360.0'))]
    )

    # Automatisch erkannte Informationen
    is_moving = models.BooleanField(_('In Bewegung'), default=True)
    estimated_arrival_time = models.DateTimeField(
        _('Geschätzte Ankunftszeit'), null=True, blank=True)
    distance_to_destination = models.DecimalField(
        _('Entfernung zum Ziel (km)'), max_digits=8, decimal_places=3, null=True, blank=True
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Standort-Update')
        verbose_name_plural = _('Standort-Updates')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.navigation_session.team.name} - {self.timestamp.strftime('%H:%M:%S')}"

    def get_coordinates(self):
        """Gibt Koordinaten als Tuple zurück"""
        return (float(self.latitude), float(self.longitude))
