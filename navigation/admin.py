from django.contrib import admin
from .models import Address, Route, NavigationSession, LocationUpdate


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['street', 'house_number', 'postal_code',
                    'city', 'has_coordinates', 'is_verified']
    list_filter = ['city', 'country', 'is_verified']
    search_fields = ['street', 'city', 'postal_code']
    readonly_fields = ['geocoded_at', 'created_at', 'updated_at']

    def has_coordinates(self, obj):
        return obj.has_coordinates
    has_coordinates.boolean = True
    has_coordinates.short_description = 'Koordinaten'


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ['from_address', 'to_address', 'transport_mode',
                    'distance_km', 'duration_minutes', 'is_cached']
    list_filter = ['transport_mode', 'is_cached', 'routing_service']
    search_fields = ['from_address__city', 'to_address__city']
    readonly_fields = ['last_updated', 'created_at']


@admin.register(NavigationSession)
class NavigationSessionAdmin(admin.ModelAdmin):
    list_display = ['team', 'event', 'current_status',
                    'started_at', 'completed_at']
    list_filter = ['current_status', 'event', 'preferred_transport_mode']
    search_fields = ['team__name', 'event__name']
    readonly_fields = ['started_at',
                       'completed_at', 'created_at', 'updated_at']

    fieldsets = (
        ('Team & Event', {
            'fields': ('team', 'event', 'optimization_run')
        }),
        ('Status', {
            'fields': ('current_status', 'current_location')
        }),
        ('Zeitstempel', {
            'fields': ('started_at', 'appetizer_arrived_at', 'main_course_arrived_at', 'dessert_arrived_at', 'completed_at')
        }),
        ('Präferenzen', {
            'fields': ('preferred_transport_mode', 'avoid_tolls', 'avoid_highways')
        }),
        ('Feedback', {
            'fields': ('rating', 'feedback', 'notes')
        }),
    )


@admin.register(LocationUpdate)
class LocationUpdateAdmin(admin.ModelAdmin):
    list_display = ['navigation_session', 'latitude',
                    'longitude', 'speed_kmh', 'is_moving', 'timestamp']
    list_filter = ['is_moving', 'navigation_session__team',
                   'navigation_session__event']
    readonly_fields = ['timestamp']

    def get_queryset(self, request):
        # Limitiere auf die letzten 1000 Einträge für bessere Performance
        return super().get_queryset(request).order_by('-timestamp')[:1000]
