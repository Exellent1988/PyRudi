"""
Cache Invalidation Signals für Running Dinner
Automatische Cache-Invalidierung bei Model-Änderungen
"""

import logging

from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from accounts.models import Team, TeamMembership
from optimization.models import OptimizationRun, TeamAssignment

from .cache_utils import EventCacheManager, OptimizationCacheManager, generate_cache_key
from .models import Event, EventOrganizer, TeamRegistration

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Event)
@receiver(post_delete, sender=Event)
def invalidate_event_cache(sender, instance, **kwargs):
    """Invalidiere Event-bezogene Caches bei Event-Änderungen"""
    
    # Event-spezifische Caches invalidieren
    EventCacheManager.invalidate_event_cache(instance.id)
    
    # Event List Caches invalidieren (dynamic import to avoid circular imports)
    try:
        from .views import (
            get_cached_available_cities,
            get_cached_event_detail_base,
            get_cached_event_list_data,
        )
        get_cached_event_list_data.clear_cache()
        get_cached_available_cities.clear_cache()
        get_cached_event_detail_base.clear_cache(instance.id)
    except ImportError:
        pass
    
    logger.info(f"🗑️ Event cache invalidated for event {instance.id} ({instance.name})")


@receiver(post_save, sender=TeamRegistration)
@receiver(post_delete, sender=TeamRegistration)
def invalidate_team_registration_cache(sender, instance, **kwargs):
    """Invalidiere Team Registration Caches"""
    
    event_id = instance.event_id
    
    # Event-bezogene Caches invalidieren
    EventCacheManager.invalidate_event_cache(event_id)
    
    # Event Detail Base Cache invalidieren (wegen team_count)
    try:
        from .views import get_cached_event_detail_base
        try:
            from .views import get_cached_event_detail_base
            get_cached_event_detail_base.clear_cache(event_id)
        except ImportError:
            pass
    except ImportError:
        pass
    
    # User-spezifische Caches für alle Team-Mitglieder invalidieren
    if instance.team:
        team_member_ids = instance.team.teammembership_set.filter(
            is_active=True
        ).values_list('user_id', flat=True)
        
        for user_id in team_member_ids:
            cache_key = generate_cache_key('user_event_data', event_id, user_id)
            cache.delete(cache_key)
    
    logger.info(f"🗑️ Team registration cache invalidated for event {event_id}")


@receiver(post_save, sender=Team)
@receiver(post_delete, sender=Team)
def invalidate_team_cache(sender, instance, **kwargs):
    """Invalidiere Team-bezogene Caches"""
    
    # Finde alle Events, in denen das Team registriert ist
    event_ids = TeamRegistration.objects.filter(
        team=instance
    ).values_list('event_id', flat=True)
    
    for event_id in event_ids:
        EventCacheManager.invalidate_event_cache(event_id)
        try:
            from .views import get_cached_event_detail_base
            get_cached_event_detail_base.clear_cache(event_id)
        except ImportError:
            pass
    
    # User-spezifische Caches für Team-Mitglieder invalidieren
    team_member_ids = instance.teammembership_set.filter(
        is_active=True
    ).values_list('user_id', flat=True)
    
    for user_id in team_member_ids:
        # Invalidiere für alle Events, in denen User aktiv ist
        for event_id in event_ids:
            cache_key = generate_cache_key('user_event_data', event_id, user_id)
            cache.delete(cache_key)
    
    logger.info(f"🗑️ Team cache invalidated for team {instance.id} ({instance.name})")


@receiver(post_save, sender=TeamMembership)
@receiver(post_delete, sender=TeamMembership)
def invalidate_team_membership_cache(sender, instance, **kwargs):
    """Invalidiere Team Membership Caches"""
    
    # Finde Events für das Team
    event_ids = TeamRegistration.objects.filter(
        team=instance.team
    ).values_list('event_id', flat=True)
    
    # User-spezifische Caches invalidieren
    for event_id in event_ids:
        cache_key = generate_cache_key('user_event_data', event_id, instance.user_id)
        cache.delete(cache_key)
    
    logger.info(f"🗑️ Team membership cache invalidated for user {instance.user_id}")


@receiver(post_save, sender=OptimizationRun)
@receiver(post_delete, sender=OptimizationRun)
def invalidate_optimization_cache(sender, instance, **kwargs):
    """Invalidiere Optimization-bezogene Caches"""
    
    event_id = instance.event_id
    
    # Optimization-spezifische Caches invalidieren
    OptimizationCacheManager.set_optimization_results(event_id, None)  # Clear latest
    
    if instance.id:
        OptimizationCacheManager.set_optimization_results(event_id, None, instance.id)  # Clear specific
    
    # Team Assignment Caches invalidieren
    for course in ['appetizer', 'main_course', 'dessert']:
        OptimizationCacheManager.set_team_assignments(event_id, None, course)
    OptimizationCacheManager.set_team_assignments(event_id, None)
    
    logger.info(f"🗑️ Optimization cache invalidated for event {event_id}, run {instance.id}")


@receiver(post_save, sender=TeamAssignment)
@receiver(post_delete, sender=TeamAssignment)
def invalidate_team_assignment_cache(sender, instance, **kwargs):
    """Invalidiere Team Assignment Caches"""
    
    optimization_run = instance.optimization_run
    event_id = optimization_run.event_id
    
    # Assignment-spezifische Caches invalidieren
    OptimizationCacheManager.set_team_assignments(event_id, None, instance.course)
    OptimizationCacheManager.set_team_assignments(event_id, None)
    
    # Optimization Results Cache invalidieren  
    from .views import get_cached_optimization_results_data
    get_cached_optimization_results_data.clear_cache(event_id, optimization_run.id)
    
    logger.info(f"🗑️ Team assignment cache invalidated for event {event_id}")


@receiver(post_save, sender=EventOrganizer)
@receiver(post_delete, sender=EventOrganizer)
def invalidate_event_organizer_cache(sender, instance, **kwargs):
    """Invalidiere Event Organizer Caches"""
    
    event_id = instance.event_id
    user_id = instance.user_id
    
    # Event Detail Cache invalidieren (wegen Organizer-Info)
    try:
        from .views import get_cached_event_detail_base
        try:
            from .views import get_cached_event_detail_base
            get_cached_event_detail_base.clear_cache(event_id)
        except ImportError:
            pass
    except ImportError:
        pass
    
    # User-spezifische Event-Daten invalidieren
    cache_key = generate_cache_key('user_event_data', event_id, user_id)
    cache.delete(cache_key)
    
    logger.info(f"🗑️ Event organizer cache invalidated for event {event_id}, user {user_id}")


def warm_cache_after_optimization(event_id, optimization_run_id):
    """
    Cache-Warming nach Optimierung
    Wird vom Optimization-Code aufgerufen, um wichtige Daten vorzuladen
    """
    from .cache_utils import warm_cache_for_event
    from .views import get_cached_optimization_results_data
    
    try:
        # Warm Event Cache
        warm_cache_for_event(event_id)
        
        # Warm Optimization Results Cache
        get_cached_optimization_results_data(event_id, optimization_run_id)
        
        logger.info(f"🔥 Cache warmed after optimization for event {event_id}")
        
    except Exception as e:
        logger.error(f"❌ Cache warming failed after optimization: {e}")


def clear_all_event_caches(event_id):
    """
    Utility function: Alle Caches für ein Event löschen
    Nützlich für Admin-Funktionen oder bei kritischen Änderungen
    """
    
    # Event-spezifische Caches
    EventCacheManager.invalidate_event_cache(event_id)
    get_cached_event_detail_base.clear_cache(event_id)
    
    # Optimization Caches
    OptimizationCacheManager.set_optimization_results(event_id, None)
    for course in ['appetizer', 'main_course', 'dessert']:
        OptimizationCacheManager.set_team_assignments(event_id, None, course)
    OptimizationCacheManager.set_team_assignments(event_id, None)
    
    # Global Caches (Event Lists)
    try:
        from .views import get_cached_available_cities, get_cached_event_list_data
        get_cached_event_list_data.clear_cache()
        get_cached_available_cities.clear_cache()
    except ImportError:
        pass
    
    logger.info(f"🧹 All caches cleared for event {event_id}")


def get_cache_health_status():
    """
    Cache Health Check für Monitoring
    Gibt Status über Cache-Nutzung zurück
    """
    from .cache_utils import get_cache_stats
    
    try:
        redis_stats = get_cache_stats()
        
        # Berechne Hit Rate
        hits = redis_stats.get('keyspace_hits', 0)
        misses = redis_stats.get('keyspace_misses', 0)
        total_ops = hits + misses
        hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0
        
        return {
            'status': 'healthy' if hit_rate > 70 else 'warning' if hit_rate > 50 else 'critical',
            'hit_rate': round(hit_rate, 1),
            'memory_used': redis_stats.get('used_memory_human', 'N/A'),
            'ops_per_sec': redis_stats.get('instantaneous_ops_per_sec', 0),
            'connected_clients': redis_stats.get('connected_clients', 0),
        }
        
    except Exception as e:
        logger.error(f"❌ Cache health check failed: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
