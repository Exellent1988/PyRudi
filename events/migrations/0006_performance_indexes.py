# Generated manually for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0005_routegeometry'),
    ]

    operations = [
        # Event Model Indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_event_status_date_idx ON events_event(status, event_date);",
            reverse_sql="DROP INDEX IF EXISTS events_event_status_date_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_event_organizer_status_idx ON events_event(organizer_id, status);",
            reverse_sql="DROP INDEX IF EXISTS events_event_organizer_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_event_date_status_idx ON events_event(event_date, status);",
            reverse_sql="DROP INDEX IF EXISTS events_event_date_status_idx;"
        ),

        # TeamRegistration Indexes - Critical for Event Management
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_teamregistration_event_status_idx ON events_teamregistration(event_id, status);",
            reverse_sql="DROP INDEX IF EXISTS events_teamregistration_event_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_teamregistration_status_registered_idx ON events_teamregistration(status, registered_at);",
            reverse_sql="DROP INDEX IF EXISTS events_teamregistration_status_registered_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_teamregistration_team_event_idx ON events_teamregistration(team_id, event_id);",
            reverse_sql="DROP INDEX IF EXISTS events_teamregistration_team_event_idx;"
        ),

        # EventOrganizer Indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_eventorganizer_event_active_idx ON events_eventorganizer(event_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS events_eventorganizer_event_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_eventorganizer_user_active_idx ON events_eventorganizer(user_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS events_eventorganizer_user_active_idx;"
        ),

        # GuestKitchen Indexes - For optimization algorithm
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_guestkitchen_event_active_idx ON events_guestkitchen(event_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS events_guestkitchen_event_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_guestkitchen_location_idx ON events_guestkitchen(latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS events_guestkitchen_location_idx;"
        ),

        # RouteGeometry Indexes - For cached routes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_routegeometry_event_coords_idx ON events_routegeometry(event_id, start_lat, start_lng, end_lat, end_lng);",
            reverse_sql="DROP INDEX IF EXISTS events_routegeometry_event_coords_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_routegeometry_start_coords_idx ON events_routegeometry(start_lat, start_lng);",
            reverse_sql="DROP INDEX IF EXISTS events_routegeometry_start_coords_idx;"
        ),

        # TeamGuestKitchenAssignment Indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_teamguestkitchenassignment_team_course_idx ON events_teamguestkitchenassignment(team_id, course, is_active);",
            reverse_sql="DROP INDEX IF EXISTS events_teamguestkitchenassignment_team_course_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS events_teamguestkitchenassignment_kitchen_active_idx ON events_teamguestkitchenassignment(guest_kitchen_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS events_teamguestkitchenassignment_kitchen_active_idx;"
        ),
    ]
