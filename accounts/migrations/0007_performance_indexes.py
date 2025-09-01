# Generated manually for performance optimization

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_add_kitchen_participation_fields'),
    ]

    operations = [
        # Team Model Indexes - Critical for optimization algorithm
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_team_location_idx ON accounts_team(latitude, longitude) WHERE latitude IS NOT NULL AND longitude IS NOT NULL;",
            reverse_sql="DROP INDEX IF EXISTS accounts_team_location_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_team_active_participation_idx ON accounts_team(is_active, participation_type);",
            reverse_sql="DROP INDEX IF EXISTS accounts_team_active_participation_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_team_kitchen_active_idx ON accounts_team(has_kitchen, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_team_kitchen_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_team_name_active_idx ON accounts_team(name, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_team_name_active_idx;"
        ),

        # TeamMembership Indexes - For team member queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teammembership_team_active_idx ON accounts_teammembership(team_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teammembership_team_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teammembership_user_active_idx ON accounts_teammembership(user_id, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teammembership_user_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teammembership_role_active_idx ON accounts_teammembership(role, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teammembership_role_active_idx;"
        ),

        # CustomUser Indexes - For user lookups
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_customuser_email_verified_idx ON accounts_customuser(email, is_verified);",
            reverse_sql="DROP INDEX IF EXISTS accounts_customuser_email_verified_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_customuser_active_staff_idx ON accounts_customuser(is_active, is_staff);",
            reverse_sql="DROP INDEX IF EXISTS accounts_customuser_active_staff_idx;"
        ),

        # TeamInvitation Indexes - For invitation management
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teaminvitation_team_status_idx ON accounts_teaminvitation(team_id, status);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teaminvitation_team_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teaminvitation_email_status_idx ON accounts_teaminvitation(email, status);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teaminvitation_email_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_teaminvitation_expires_status_idx ON accounts_teaminvitation(expires_at, status);",
            reverse_sql="DROP INDEX IF EXISTS accounts_teaminvitation_expires_status_idx;"
        ),

        # DietaryRestriction Indexes - For allergy/diet queries
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_dietaryrestriction_category_active_idx ON accounts_dietaryrestriction(category, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_dietaryrestriction_category_active_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS accounts_dietaryrestriction_severity_active_idx ON accounts_dietaryrestriction(severity, is_active);",
            reverse_sql="DROP INDEX IF EXISTS accounts_dietaryrestriction_severity_active_idx;"
        ),
    ]
