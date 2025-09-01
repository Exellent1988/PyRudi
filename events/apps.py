from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'events'
    
    def ready(self):
        """Import cache signals when app is ready"""
        try:
            import events.cache_signals  # noqa
        except ImportError:
            pass