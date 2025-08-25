from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json


class OptimizationRun(models.Model):
    """Modell für Optimierungsläufe der Running Dinner Zuweisungen"""

    STATUS_CHOICES = [
        ('pending', _('Wartend')),
        ('running', _('Läuft')),
        ('completed', _('Abgeschlossen')),
        ('failed', _('Fehlgeschlagen')),
        ('cancelled', _('Abgebrochen')),
    ]

    event = models.ForeignKey(
        'events.Event',
        on_delete=models.CASCADE,
        related_name='optimization_runs',
        verbose_name=_('Event')
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Optimierungsparameter
    max_distance_weight = models.DecimalField(
        _('Entfernung Gewichtung'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.4'),
        validators=[MinValueValidator(
            Decimal('0.0')), MaxValueValidator(Decimal('1.0'))],
        help_text=_('Gewichtung für Entfernungsminimierung (0.0-1.0)')
    )
    preference_weight = models.DecimalField(
        _('Präferenz Gewichtung'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.3'),
        validators=[MinValueValidator(
            Decimal('0.0')), MaxValueValidator(Decimal('1.0'))],
        help_text=_('Gewichtung für Team-Präferenzen (0.0-1.0)')
    )
    balance_weight = models.DecimalField(
        _('Ausgewogenheit Gewichtung'),
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.3'),
        validators=[MinValueValidator(
            Decimal('0.0')), MaxValueValidator(Decimal('1.0'))],
        help_text=_('Gewichtung für Kursverteilung (0.0-1.0)')
    )

    # Algorithmus-Einstellungen
    algorithm = models.CharField(
        _('Algorithmus'),
        max_length=20,
        choices=[
            ('greedy', _('Greedy-Algorithmus')),
            ('genetic', _('Genetischer Algorithmus')),
            ('simulated_annealing', _('Simulated Annealing')),
            ('linear_programming', _('Lineare Programmierung')),
        ],
        default='genetic'
    )
    max_iterations = models.PositiveIntegerField(
        _('Maximale Iterationen'),
        default=1000,
        help_text=_('Maximale Anzahl Algorithmus-Iterationen')
    )
    time_limit_seconds = models.PositiveIntegerField(
        _('Zeitlimit (Sekunden)'),
        default=300,
        help_text=_('Maximale Laufzeit der Optimierung')
    )

    # Ergebnisse
    total_distance = models.DecimalField(
        _('Gesamtentfernung (km)'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    objective_value = models.DecimalField(
        _('Zielfunktionswert'),
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text=_('Gesamtbewertung der Lösung')
    )
    iterations_completed = models.PositiveIntegerField(
        _('Durchgeführte Iterationen'),
        null=True,
        blank=True
    )
    execution_time = models.DecimalField(
        _('Ausführungszeit (Sekunden)'),
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Metadaten
    started_at = models.DateTimeField(
        _('Gestartet um'),
        null=True,
        blank=True
    )
    completed_at = models.DateTimeField(
        _('Abgeschlossen um'),
        null=True,
        blank=True
    )
    error_message = models.TextField(
        _('Fehlermeldung'),
        blank=True
    )
    log_data = models.JSONField(
        _('Log-Daten'),
        default=dict,
        blank=True,
        help_text=_('Detaillierte Algorithmus-Logs')
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Optimierungslauf')
        verbose_name_plural = _('Optimierungsläufe')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event.name} - {self.get_status_display()} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"

    @property
    def is_running(self):
        return self.status == 'running'

    @property
    def is_completed(self):
        return self.status == 'completed'


class TeamAssignment(models.Model):
    """Modell für die Zuweisungen von Teams zu Kursen und Hosts"""

    optimization_run = models.ForeignKey(
        OptimizationRun,
        on_delete=models.CASCADE,
        related_name='team_assignments',
        verbose_name=_('Optimierungslauf')
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='assignments',
        verbose_name=_('Team')
    )
    course = models.CharField(
        _('Kurs'),
        max_length=20,
        choices=[
            ('appetizer', _('Vorspeise')),
            ('main_course', _('Hauptgang')),
            ('dessert', _('Nachspeise')),
        ]
    )

    # Hosting-Zuweisungen
    hosts_appetizer = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='hosted_appetizer_assignments',
        verbose_name=_('Vorspeise bei'),
        null=True,
        blank=True
    )
    hosts_main_course = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='hosted_main_course_assignments',
        verbose_name=_('Hauptgang bei'),
        null=True,
        blank=True
    )
    hosts_dessert = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='hosted_dessert_assignments',
        verbose_name=_('Nachspeise bei'),
        null=True,
        blank=True
    )

    # Gäste für den eigenen Kurs (wenn das Team hostet)
    guests = models.ManyToManyField(
        'accounts.Team',
        related_name='guest_assignments',
        verbose_name=_('Gäste'),
        blank=True
    )

    # Berechnete Entfernungen
    distance_to_appetizer = models.DecimalField(
        _('Entfernung zur Vorspeise (km)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    distance_to_main_course = models.DecimalField(
        _('Entfernung zum Hauptgang (km)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    distance_to_dessert = models.DecimalField(
        _('Entfernung zur Nachspeise (km)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    total_distance = models.DecimalField(
        _('Gesamtentfernung (km)'),
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Bewertungen
    preference_score = models.DecimalField(
        _('Präferenz-Score'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Bewertung wie gut Präferenzen erfüllt wurden')
    )
    constraint_violations = models.JSONField(
        _('Constraint-Verletzungen'),
        default=list,
        blank=True,
        help_text=_('Liste der verletzten Einschränkungen')
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Team-Zuweisung')
        verbose_name_plural = _('Team-Zuweisungen')
        unique_together = ['optimization_run', 'team']
        ordering = ['team__name']

    def __str__(self):
        return f"{self.team.name} - {self.get_course_display()}"

    @property
    def hosting_team(self):
        """Gibt das Team zurück, bei dem dieses Team für seinen zugewiesenen Kurs ist"""
        if self.course == 'appetizer':
            return self.hosts_appetizer
        elif self.course == 'main_course':
            return self.hosts_main_course
        elif self.course == 'dessert':
            return self.hosts_dessert
        return None

    def get_distance_for_course(self, course):
        """Gibt die Entfernung für einen bestimmten Kurs zurück"""
        if course == 'appetizer':
            return self.distance_to_appetizer
        elif course == 'main_course':
            return self.distance_to_main_course
        elif course == 'dessert':
            return self.distance_to_dessert
        return None


class OptimizationConstraint(models.Model):
    """Modell für benutzerdefinierte Optimierungs-Constraints"""

    CONSTRAINT_TYPES = [
        ('team_separation', _('Team-Trennung')),
        ('team_grouping', _('Team-Gruppierung')),
        ('dietary_restriction', _('Diäteinschränkung')),
        ('accessibility', _('Barrierefreiheit')),
        ('distance_limit', _('Entfernungslimit')),
        ('hosting_preference', _('Hosting-Präferenz')),
    ]

    optimization_run = models.ForeignKey(
        OptimizationRun,
        on_delete=models.CASCADE,
        related_name='constraints',
        verbose_name=_('Optimierungslauf')
    )
    constraint_type = models.CharField(
        _('Constraint-Typ'),
        max_length=30,
        choices=CONSTRAINT_TYPES
    )
    name = models.CharField(
        _('Name'),
        max_length=100
    )
    description = models.TextField(
        _('Beschreibung'),
        blank=True
    )
    is_hard_constraint = models.BooleanField(
        _('Harte Einschränkung'),
        default=True,
        help_text=_('Muss erfüllt werden (true) oder ist nur Präferenz (false)')
    )
    weight = models.DecimalField(
        _('Gewichtung'),
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        help_text=_('Gewichtung bei weichen Einschränkungen')
    )

    # Flexible Parameter als JSON
    parameters = models.JSONField(
        _('Parameter'),
        default=dict,
        help_text=_('Constraint-spezifische Parameter')
    )

    is_active = models.BooleanField(
        _('Aktiv'),
        default=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Optimierungs-Constraint')
        verbose_name_plural = _('Optimierungs-Constraints')
        ordering = ['constraint_type', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_constraint_type_display()})"
