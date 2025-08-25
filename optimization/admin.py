from django.contrib import admin
from .models import OptimizationRun, TeamAssignment, OptimizationConstraint


@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = ['event', 'status', 'algorithm',
                    'total_distance', 'objective_value', 'created_at']
    list_filter = ['status', 'algorithm', 'created_at']
    search_fields = ['event__name']
    readonly_fields = ['total_distance', 'objective_value',
                       'iterations_completed', 'execution_time', 'started_at', 'completed_at']
    fieldsets = (
        ('Event', {
            'fields': ('event', 'status')
        }),
        ('Algorithmus-Einstellungen', {
            'fields': ('algorithm', 'max_iterations', 'time_limit_seconds')
        }),
        ('Gewichtungen', {
            'fields': ('max_distance_weight', 'preference_weight', 'balance_weight')
        }),
        ('Ergebnisse', {
            'fields': ('total_distance', 'objective_value', 'iterations_completed', 'execution_time')
        }),
        ('Zeitstempel', {
            'fields': ('started_at', 'completed_at', 'created_at', 'updated_at')
        }),
    )


@admin.register(TeamAssignment)
class TeamAssignmentAdmin(admin.ModelAdmin):
    list_display = ['team', 'course', 'optimization_run', 'total_distance']
    list_filter = ['course', 'optimization_run__event']
    search_fields = ['team__name', 'optimization_run__event__name']
    readonly_fields = ['total_distance', 'distance_to_appetizer',
                       'distance_to_main_course', 'distance_to_dessert']


@admin.register(OptimizationConstraint)
class OptimizationConstraintAdmin(admin.ModelAdmin):
    list_display = ['name', 'constraint_type',
                    'optimization_run', 'is_hard_constraint', 'is_active']
    list_filter = ['constraint_type', 'is_hard_constraint', 'is_active']
    search_fields = ['name', 'optimization_run__event__name']
