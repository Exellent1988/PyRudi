"""
Redis Caching Utilities für Running Dinner Performance-Optimierung
Strategische Cache-Points für große Events (1000+ Teams)
"""

import hashlib
import json
import logging
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache Timeouts (in Sekunden)
CACHE_TIMEOUTS = {
    'event_summary': 300,          # 5 Minuten - Event Statistiken
    'team_registrations': 180,     # 3 Minuten - Team-Listen
    'optimization_results': 600,   # 10 Minuten - Optimization Ergebnisse
    'route_distances': 3600,       # 1 Stunde - Entfernungsberechnungen
    'admin_dashboard': 120,        # 2 Minuten - Admin Dashboard Daten
    'event_detail': 300,           # 5 Minuten - Event Details
    'team_assignments': 1800,      # 30 Minuten - Team Zuordnungen
    'geographic_queries': 900,     # 15 Minuten - Geo-Abfragen
}

# Cache Key Prefixes für bessere Organisation
CACHE_PREFIXES = {
    'event': 'evt',
    'team': 'team',
    'optimization': 'opt',
    'route': 'route',
    'admin': 'admin',
    'api': 'api',
}


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generiert konsistente Cache-Keys mit Hashing für lange Parameter
    """
    # Erstelle String aus allen Parametern
    key_parts = [CACHE_PREFIXES.get(prefix, prefix)]
    
    # Füge args hinzu
    for arg in args:
        if isinstance(arg, (dict, list)):
            key_parts.append(hashlib.md5(json.dumps(arg, sort_keys=True).encode()).hexdigest()[:8])
        else:
            key_parts.append(str(arg))
    
    # Füge kwargs hinzu
    if kwargs:
        kwargs_str = json.dumps(kwargs, sort_keys=True)
        key_parts.append(hashlib.md5(kwargs_str.encode()).hexdigest()[:8])
    
    return ':'.join(key_parts)


def cache_function(timeout_key: str = None, timeout: int = 300):
    """
    Decorator für Function-Level Caching mit automatischer Key-Generierung
    
    Usage:
        @cache_function('event_summary', 300)
        def get_event_statistics(event_id):
            # expensive calculation
            return data
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generiere Cache-Key basierend auf Function Name und Parametern
            cache_key = generate_cache_key(func.__name__, *args, **kwargs)
            
            # Versuche aus Cache zu laden
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_result
            
            # Führe Function aus und cache das Ergebnis
            result = func(*args, **kwargs)
            
            # Bestimme Timeout
            actual_timeout = CACHE_TIMEOUTS.get(timeout_key, timeout)
            cache.set(cache_key, result, actual_timeout)
            
            logger.debug(f"Cache SET: {cache_key} (timeout: {actual_timeout}s)")
            return result
        
        # Füge cache_clear Methode hinzu
        def clear_cache(*args, **kwargs):
            cache_key = generate_cache_key(func.__name__, *args, **kwargs)
            cache.delete(cache_key)
            logger.debug(f"Cache CLEAR: {cache_key}")
        
        wrapper.clear_cache = clear_cache
        return wrapper
    return decorator


class EventCacheManager:
    """
    Cache-Manager für Event-bezogene Daten mit intelligenter Invalidierung
    """
    
    @staticmethod
    def get_event_summary(event_id: int) -> dict:
        """Cached Event Summary mit Statistiken"""
        cache_key = generate_cache_key('event', 'summary', event_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_event_summary(event_id: int, data: dict):
        """Cache Event Summary"""
        cache_key = generate_cache_key('event', 'summary', event_id)
        cache.set(cache_key, data, CACHE_TIMEOUTS['event_summary'])
    
    @staticmethod
    def get_team_registrations(event_id: int) -> list:
        """Cached Team Registrations"""
        cache_key = generate_cache_key('event', 'teams', event_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_team_registrations(event_id: int, data: list):
        """Cache Team Registrations"""
        cache_key = generate_cache_key('event', 'teams', event_id)
        cache.set(cache_key, data, CACHE_TIMEOUTS['team_registrations'])
    
    @staticmethod
    def invalidate_event_cache(event_id: int):
        """Invalidiere alle Event-bezogenen Caches"""
        patterns = [
            generate_cache_key('event', 'summary', event_id),
            generate_cache_key('event', 'teams', event_id),
            generate_cache_key('event', 'detail', event_id),
            generate_cache_key('opt', 'results', event_id),
        ]
        
        for pattern in patterns:
            cache.delete(pattern)
        
        logger.info(f"🗑️ Event cache invalidated for event {event_id}")


class OptimizationCacheManager:
    """
    Cache-Manager für Optimization-Ergebnisse
    """
    
    @staticmethod
    def get_optimization_results(event_id: int, run_id: int = None) -> dict:
        """Cached Optimization Results"""
        if run_id:
            cache_key = generate_cache_key('opt', 'results', event_id, run_id)
        else:
            cache_key = generate_cache_key('opt', 'latest', event_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_optimization_results(event_id: int, data: dict, run_id: int = None):
        """Cache Optimization Results"""
        if run_id:
            cache_key = generate_cache_key('opt', 'results', event_id, run_id)
            # Längeres Timeout für spezifische Run-Ergebnisse
            timeout = CACHE_TIMEOUTS['optimization_results'] * 2
        else:
            cache_key = generate_cache_key('opt', 'latest', event_id)
            timeout = CACHE_TIMEOUTS['optimization_results']
        
        cache.set(cache_key, data, timeout)
    
    @staticmethod
    def get_team_assignments(event_id: int, course: str = None) -> list:
        """Cached Team Assignments"""
        if course:
            cache_key = generate_cache_key('opt', 'assignments', event_id, course)
        else:
            cache_key = generate_cache_key('opt', 'assignments', event_id)
        return cache.get(cache_key)
    
    @staticmethod
    def set_team_assignments(event_id: int, data: list, course: str = None):
        """Cache Team Assignments"""
        if course:
            cache_key = generate_cache_key('opt', 'assignments', event_id, course)
        else:
            cache_key = generate_cache_key('opt', 'assignments', event_id)
        
        cache.set(cache_key, data, CACHE_TIMEOUTS['team_assignments'])


class RouteCacheManager:
    """
    Cache-Manager für Routen und Entfernungsberechnungen
    """
    
    @staticmethod
    def get_route_distance(start_coords: tuple, end_coords: tuple) -> float:
        """Cached Route Distance"""
        cache_key = generate_cache_key('route', 'distance', 
                                     f"{start_coords[0]:.4f}_{start_coords[1]:.4f}",
                                     f"{end_coords[0]:.4f}_{end_coords[1]:.4f}")
        return cache.get(cache_key)
    
    @staticmethod
    def set_route_distance(start_coords: tuple, end_coords: tuple, distance: float):
        """Cache Route Distance"""
        cache_key = generate_cache_key('route', 'distance',
                                     f"{start_coords[0]:.4f}_{start_coords[1]:.4f}",
                                     f"{end_coords[0]:.4f}_{end_coords[1]:.4f}")
        cache.set(cache_key, distance, CACHE_TIMEOUTS['route_distances'])
    
    @staticmethod
    def get_route_geometry(start_coords: tuple, end_coords: tuple) -> list:
        """Cached Route Geometry"""
        cache_key = generate_cache_key('route', 'geometry',
                                     f"{start_coords[0]:.4f}_{start_coords[1]:.4f}",
                                     f"{end_coords[0]:.4f}_{end_coords[1]:.4f}")
        return cache.get(cache_key)
    
    @staticmethod
    def set_route_geometry(start_coords: tuple, end_coords: tuple, geometry: list):
        """Cache Route Geometry"""
        cache_key = generate_cache_key('route', 'geometry',
                                     f"{start_coords[0]:.4f}_{start_coords[1]:.4f}",
                                     f"{end_coords[0]:.4f}_{end_coords[1]:.4f}")
        cache.set(cache_key, geometry, CACHE_TIMEOUTS['route_distances'])


class AdminCacheManager:
    """
    Cache-Manager für Admin Dashboard Performance
    """
    
    @staticmethod
    def get_dashboard_stats() -> dict:
        """Cached Admin Dashboard Statistics"""
        cache_key = generate_cache_key('admin', 'dashboard', 'stats')
        return cache.get(cache_key)
    
    @staticmethod
    def set_dashboard_stats(data: dict):
        """Cache Admin Dashboard Statistics"""
        cache_key = generate_cache_key('admin', 'dashboard', 'stats')
        cache.set(cache_key, data, CACHE_TIMEOUTS['admin_dashboard'])
    
    @staticmethod
    def get_recent_activities() -> list:
        """Cached Recent Activities"""
        cache_key = generate_cache_key('admin', 'activities', 'recent')
        return cache.get(cache_key)
    
    @staticmethod
    def set_recent_activities(data: list):
        """Cache Recent Activities"""
        cache_key = generate_cache_key('admin', 'activities', 'recent')
        cache.set(cache_key, data, CACHE_TIMEOUTS['admin_dashboard'])


def invalidate_cache_patterns(*patterns):
    """
    Invalidiere Cache nach Patterns (für Cache-Warming und Cleanup)
    """
    # In einer realen Implementation würde man hier redis-py verwenden
    # für Pattern-based Deletion. Für jetzt eine einfache Lösung:
    for pattern in patterns:
        cache.delete(pattern)
    
    logger.info(f"🗑️ Cache patterns invalidated: {patterns}")


def warm_cache_for_event(event_id: int):
    """
    Cache-Warming für ein Event - lädt wichtige Daten vor
    """
    from events.models import Event, TeamRegistration
    from optimization.models import OptimizationRun
    
    try:
        event = Event.objects.get(id=event_id)
        
        # Warm Event Summary
        team_count = TeamRegistration.objects.filter(event=event, status='confirmed').count()
        event_summary = {
            'id': event.id,
            'name': event.name,
            'team_count': team_count,
            'status': event.status,
            'event_date': event.event_date.isoformat() if event.event_date else None,
        }
        EventCacheManager.set_event_summary(event_id, event_summary)
        
        # Warm Team Registrations
        registrations = list(TeamRegistration.objects.filter(
            event=event, status='confirmed'
        ).select_related('team').values(
            'id', 'team__name', 'team__latitude', 'team__longitude', 'registered_at'
        ))
        EventCacheManager.set_team_registrations(event_id, registrations)
        
        # Warm Latest Optimization Results
        latest_run = OptimizationRun.objects.filter(
            event=event, status='completed'
        ).order_by('-completed_at').first()
        
        if latest_run:
            optimization_data = {
                'run_id': latest_run.id,
                'total_distance': latest_run.total_distance,
                'completed_at': latest_run.completed_at.isoformat(),
                'team_count': latest_run.teamassignment_set.count(),
            }
            OptimizationCacheManager.set_optimization_results(event_id, optimization_data)
        
        logger.info(f"🔥 Cache warmed for event {event_id}")
        
    except Exception as e:
        logger.error(f"❌ Cache warming failed for event {event_id}: {e}")


def get_cache_stats() -> dict:
    """
    Hole Redis Cache-Statistiken für Monitoring
    """
    try:
        from django_redis import get_redis_connection
        redis_conn = get_redis_connection("default")
        
        info = redis_conn.info()
        return {
            'connected_clients': info.get('connected_clients', 0),
            'used_memory_human': info.get('used_memory_human', '0B'),
            'used_memory_peak_human': info.get('used_memory_peak_human', '0B'),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'instantaneous_ops_per_sec': info.get('instantaneous_ops_per_sec', 0),
        }
    except Exception as e:
        logger.error(f"❌ Failed to get cache stats: {e}")
        return {}
