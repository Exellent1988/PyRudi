from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator, EmailValidator
from django.utils.translation import gettext_lazy as _


class DietaryRestriction(models.Model):
    """Modell für standardisierte Ernährungseinschränkungen"""

    CATEGORY_CHOICES = [
        ('allergy', _('Allergie')),
        ('intolerance', _('Unverträglichkeit')),
        ('diet', _('Diät/Lebensstil')),
        ('religion', _('Religiöse Einschränkung')),
    ]

    SEVERITY_CHOICES = [
        ('mild', _('Leicht')),
        ('moderate', _('Moderat')),
        ('severe', _('Schwer')),
        ('life_threatening', _('Lebensbedrohlich')),
    ]

    name = models.CharField(
        _('Name'),
        max_length=100,
        unique=True
    )
    category = models.CharField(
        _('Kategorie'),
        max_length=20,
        choices=CATEGORY_CHOICES
    )
    severity = models.CharField(
        _('Schweregrad'),
        max_length=20,
        choices=SEVERITY_CHOICES,
        default='mild'
    )
    description = models.TextField(
        _('Beschreibung'),
        blank=True,
        help_text=_('Zusätzliche Informationen zu dieser Einschränkung')
    )
    common_ingredients = models.TextField(
        _('Häufige problematische Zutaten'),
        blank=True,
        help_text=_('Kommagetrennte Liste problematischer Zutaten')
    )
    alternatives = models.TextField(
        _('Alternativen/Ersatzstoffe'),
        blank=True,
        help_text=_('Empfohlene Alternativen oder Ersatzstoffe')
    )
    emergency_info = models.TextField(
        _('Notfall-Information'),
        blank=True,
        help_text=_('Wichtige Informationen für Notfälle')
    )
    is_active = models.BooleanField(
        _('Aktiv'),
        default=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Ernährungseinschränkung')
        verbose_name_plural = _('Ernährungseinschränkungen')
        ordering = ['category', 'severity', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    @property
    def is_critical(self):
        return self.severity in ['severe', 'life_threatening']

    @property
    def css_class(self):
        """CSS-Klasse basierend auf Schweregrad"""
        return {
            'mild': 'info',
            'moderate': 'warning',
            'severe': 'danger',
            'life_threatening': 'danger'
        }.get(self.severity, 'secondary')


class CustomUser(AbstractUser):
    """Erweiterte User-Klasse für zusätzliche Funktionalität"""

    email = models.EmailField(
        _('E-Mail Adresse'),
        unique=True,
        validators=[EmailValidator()]
    )
    phone_number = models.CharField(
        _('Telefonnummer'),
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message='Telefonnummer muss im Format: "+499999999" eingegeben werden. Bis zu 15 Zeichen erlaubt.'
        )]
    )
    date_of_birth = models.DateField(
        _('Geburtsdatum'),
        null=True,
        blank=True
    )
    # Strukturierte Ernährungseinschränkungen
    dietary_restrictions_structured = models.ManyToManyField(
        DietaryRestriction,
        blank=True,
        verbose_name=_('Ernährungseinschränkungen'),
        help_text=_('Wähle deine Allergien und Diäteinschränkungen aus')
    )
    dietary_restrictions = models.TextField(
        _('Zusätzliche Ernährungshinweise'),
        blank=True,
        help_text=_('Weitere Details zu Allergien, Diäten, etc.')
    )
    emergency_contact = models.CharField(
        _('Notfallkontakt'),
        max_length=100,
        blank=True
    )
    emergency_phone = models.CharField(
        _('Notfall-Telefonnummer'),
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message='Telefonnummer muss im Format: "+499999999" eingegeben werden.'
        )]
    )
    profile_picture = models.ImageField(
        _('Profilbild'),
        upload_to='profiles/',
        blank=True,
        null=True
    )
    is_verified = models.BooleanField(
        _('E-Mail verifiziert'),
        default=False
    )
    privacy_accepted = models.BooleanField(
        _('Datenschutz akzeptiert'),
        default=False
    )
    newsletter_consent = models.BooleanField(
        _('Newsletter-Einverständnis'),
        default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = _('Benutzer')
        verbose_name_plural = _('Benutzer')

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_dietary_restrictions(self):
        """Prüft ob User Ernährungseinschränkungen hat"""
        return (self.dietary_restrictions_structured.exists() or
                bool(self.dietary_restrictions.strip()))

    @property
    def critical_allergies(self):
        """Gibt kritische Allergien zurück"""
        return self.dietary_restrictions_structured.filter(
            severity__in=['severe', 'life_threatening']
        )

    @property
    def dietary_summary(self):
        """Kurze Zusammenfassung der Ernährungseinschränkungen"""
        restrictions = list(self.dietary_restrictions_structured.all())
        if len(restrictions) > 3:
            return f"{restrictions[0].name}, {restrictions[1].name} +{len(restrictions)-2} weitere"
        elif restrictions:
            return ", ".join([r.name for r in restrictions])
        elif self.dietary_restrictions:
            return self.dietary_restrictions[:50] + ("..." if len(self.dietary_restrictions) > 50 else "")
        return "Keine besonderen Einschränkungen"

    def get_emergency_dietary_info(self):
        """Wichtige Notfall-Informationen zu Allergien"""
        critical = self.critical_allergies
        if critical.exists():
            return {
                'has_critical': True,
                'allergies': [
                    {
                        'name': allergy.name,
                        'emergency_info': allergy.emergency_info,
                        'severity': allergy.get_severity_display()
                    } for allergy in critical
                ],
                'emergency_contact': self.emergency_contact,
                'emergency_phone': self.emergency_phone
            }
        return {'has_critical': False}


class Team(models.Model):
    """Modell für Running Dinner Teams"""

    name = models.CharField(
        _('Team-Name'),
        max_length=100,
        unique=True
    )
    description = models.TextField(
        _('Team-Beschreibung'),
        blank=True,
        help_text=_('Kurze Beschreibung des Teams')
    )
    members = models.ManyToManyField(
        CustomUser,
        through='TeamMembership',
        verbose_name=_('Team-Mitglieder')
    )
    max_members = models.PositiveIntegerField(
        _('Maximale Mitgliederzahl'),
        default=2,
        help_text=_('Standard: 2 Personen pro Team')
    )
    home_address = models.TextField(
        _('Hausadresse'),
        help_text=_('Adresse wo das Team kocht/empfängt')
    )
    latitude = models.DecimalField(
        _('Breitengrad'),
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        _('Längengrad'),
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True
    )
    cooking_preferences = models.TextField(
        _('Koch-Präferenzen'),
        blank=True,
        help_text=_('Bevorzugte Küche, Spezialitäten, etc.')
    )
    kitchen_equipment = models.TextField(
        _('Küchenausstattung'),
        blank=True,
        help_text=_('Verfügbare Küchengeräte und -ausstattung')
    )
    max_guests = models.PositiveIntegerField(
        _('Maximale Gästeanzahl'),
        default=6,
        help_text=_('Wie viele Gäste können maximal bewirtet werden?')
    )
    accessibility_notes = models.TextField(
        _('Barrierefreiheit'),
        blank=True,
        help_text=_('Informationen zur Barrierefreiheit der Wohnung')
    )
    contact_person = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='led_teams',
        verbose_name=_('Hauptansprechpartner')
    )
    is_active = models.BooleanField(
        _('Aktiv'),
        default=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Team')
        verbose_name_plural = _('Teams')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.count()

    @property
    def is_full(self):
        return self.member_count >= self.max_members

    def can_host(self, guest_count):
        """Prüft ob das Team die Anzahl Gäste bewirten kann"""
        return guest_count <= self.max_guests

    @property
    def team_dietary_restrictions(self):
        """Gibt alle Ernährungseinschränkungen des Teams zurück"""
        from django.db.models import Q
        restrictions = DietaryRestriction.objects.filter(
            customuser__teammembership__team=self,
            customuser__teammembership__is_active=True
        ).distinct()
        return restrictions

    @property
    def critical_team_allergies(self):
        """Gibt kritische Allergien aller Team-Mitglieder zurück"""
        return self.team_dietary_restrictions.filter(
            severity__in=['severe', 'life_threatening']
        )

    @property
    def team_dietary_summary(self):
        """Zusammenfassung aller Team-Diäteinschränkungen"""
        restrictions = list(self.team_dietary_restrictions)
        member_texts = []

        for member in self.members.filter(teammembership__is_active=True):
            if member.dietary_restrictions.strip():
                member_texts.append(
                    f"{member.first_name}: {member.dietary_restrictions}")

        summary = []
        if restrictions:
            restriction_names = [r.name for r in restrictions]
            summary.append("Allergien/Diäten: " + ", ".join(restriction_names))

        if member_texts:
            summary.extend(member_texts)

        return summary if summary else ["Keine besonderen Einschränkungen"]

    def get_team_emergency_info(self):
        """Notfall-Informationen für das gesamte Team"""
        critical_info = []
        for member in self.members.filter(teammembership__is_active=True):
            member_info = member.get_emergency_dietary_info()
            if member_info['has_critical']:
                critical_info.append({
                    'member': member.full_name,
                    'member_email': member.email,
                    **member_info
                })
        return critical_info

    def is_compatible_with_dietary_restrictions(self, other_team):
        """Prüft ob zwei Teams bzgl. Ernährungseinschränkungen kompatibel sind"""
        # Diese Methode kann später für das Matching verwendet werden
        our_restrictions = set(
            self.team_dietary_restrictions.values_list('id', flat=True))
        their_restrictions = set(
            other_team.team_dietary_restrictions.values_list('id', flat=True))

        # Hier können komplexere Regeln implementiert werden
        # z.B. Vegetarier sollten nicht bei Fleischliebhabern essen
        return True  # Vorerst immer kompatibel


class TeamMembership(models.Model):
    """Zwischen-Tabelle für Team-Mitgliedschaften"""

    ROLE_CHOICES = [
        ('leader', _('Team-Leader')),
        ('member', _('Mitglied')),
        ('substitute', _('Ersatzmitglied')),
    ]

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        verbose_name=_('Benutzer')
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        verbose_name=_('Team')
    )
    role = models.CharField(
        _('Rolle'),
        max_length=20,
        choices=ROLE_CHOICES,
        default='member'
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(
        _('Aktiv'),
        default=True
    )

    class Meta:
        verbose_name = _('Team-Mitgliedschaft')
        verbose_name_plural = _('Team-Mitgliedschaften')
        unique_together = ['user', 'team']
        ordering = ['team__name', 'role']

    def __str__(self):
        return f"{self.user.full_name} - {self.team.name} ({self.get_role_display()})"


class TeamInvitation(models.Model):
    """Modell für Team-Einladungen"""

    STATUS_CHOICES = [
        ('pending', _('Ausstehend')),
        ('accepted', _('Angenommen')),
        ('declined', _('Abgelehnt')),
        ('expired', _('Abgelaufen')),
    ]

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        verbose_name=_('Team')
    )
    invited_by = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='sent_invitations',
        verbose_name=_('Eingeladen von')
    )
    email = models.EmailField(
        _('E-Mail Adresse'),
        validators=[EmailValidator()]
    )
    token = models.CharField(
        _('Einladungs-Token'),
        max_length=100,
        unique=True
    )
    status = models.CharField(
        _('Status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    message = models.TextField(
        _('Nachricht'),
        blank=True,
        help_text=_('Persönliche Nachricht an den Eingeladenen')
    )
    expires_at = models.DateTimeField(
        _('Läuft ab am')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(
        _('Beantwortet am'),
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = _('Team-Einladung')
        verbose_name_plural = _('Team-Einladungen')
        ordering = ['-created_at']

    def __str__(self):
        return f"Einladung für {self.email} zu {self.team.name}"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def accept(self, user):
        """Einladung annehmen"""
        if self.status == 'pending' and not self.is_expired:
            self.status = 'accepted'
            self.responded_at = timezone.now()
            self.save()

            # Team-Mitgliedschaft erstellen
            TeamMembership.objects.get_or_create(
                user=user,
                team=self.team,
                defaults={'role': 'member'}
            )
            return True
        return False

    def decline(self):
        """Einladung ablehnen"""
        if self.status == 'pending':
            self.status = 'declined'
            self.responded_at = timezone.now()
            self.save()
            return True
        return False
