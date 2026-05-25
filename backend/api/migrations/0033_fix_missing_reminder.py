from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0032_alter_stockalert_unique_together_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE TABLE IF NOT EXISTS api_reminder ("
                "id SERIAL PRIMARY KEY, "
                "business_id INTEGER NOT NULL, "
                "title VARCHAR(255) NOT NULL, "
                "description TEXT NULL, "
                "due_date TIMESTAMPTZ NOT NULL, "
                "is_completed BOOLEAN NOT NULL DEFAULT FALSE, "
                "created_at TIMESTAMPTZ NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL"
                ");"
                "DO $$ BEGIN "
                "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'api_reminder_business_id_fkey') THEN "
                "ALTER TABLE api_reminder "
                "ADD CONSTRAINT api_reminder_business_id_fkey "
                "FOREIGN KEY (business_id) REFERENCES api_business(id) "
                "DEFERRABLE INITIALLY DEFERRED; "
                "END IF; "
                "END $$;"
            ),
            reverse_sql=(
                "ALTER TABLE IF EXISTS api_reminder "
                "DROP CONSTRAINT IF EXISTS api_reminder_business_id_fkey;"
                "DROP TABLE IF EXISTS api_reminder;"
            ),
        ),
    ]
