# Generated manually for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('optimization', '0001_initial'),
    ]

    operations = [
        # OptimizationRun Indexes - Critical for optimization results
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_optimizationrun_event_status_idx ON optimization_optimizationrun(event_id, status);",
            reverse_sql="DROP INDEX IF EXISTS optimization_optimizationrun_event_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_optimizationrun_event_completed_idx ON optimization_optimizationrun(event_id, completed_at DESC) WHERE completed_at IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_optimizationrun_event_completed_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_optimizationrun_status_started_idx ON optimization_optimizationrun(status, started_at);",
            reverse_sql="DROP INDEX IF EXISTS optimization_optimizationrun_status_started_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_optimizationrun_algorithm_status_idx ON optimization_optimizationrun(algorithm, status);",
            reverse_sql="DROP INDEX IF EXISTS optimization_optimizationrun_algorithm_status_idx;"
        ),

        # TeamAssignment Indexes - Most critical for large events
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_optimization_team_idx ON optimization_teamassignment(optimization_run_id, team_id);",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_optimization_team_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_optimization_course_idx ON optimization_teamassignment(optimization_run_id, course);",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_optimization_course_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_team_course_idx ON optimization_teamassignment(team_id, course);",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_team_course_idx;"
        ),

        # Host assignment indexes - for routing queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_hosts_appetizer_idx ON optimization_teamassignment(hosts_appetizer_id) WHERE hosts_appetizer_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_hosts_appetizer_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_hosts_main_course_idx ON optimization_teamassignment(hosts_main_course_id) WHERE hosts_main_course_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_hosts_main_course_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_hosts_dessert_idx ON optimization_teamassignment(hosts_dessert_id) WHERE hosts_dessert_id IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_hosts_dessert_idx;"
        ),

        # Performance metrics indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_teamassignment_distance_idx ON optimization_teamassignment(total_distance) WHERE total_distance IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_teamassignment_distance_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS optimization_optimizationrun_total_distance_idx ON optimization_optimizationrun(total_distance) WHERE total_distance IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS optimization_optimizationrun_total_distance_idx;"
        ),
    ]
