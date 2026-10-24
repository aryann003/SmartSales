"""Create the analytics SQL views so a fresh database is fully usable."""
from django.db import migrations

from analytics import sqlviews


def forwards(apps, schema_editor):
    sqlviews.create_views(schema_editor.connection)


def backwards(apps, schema_editor):
    sqlviews.drop_views(schema_editor.connection)


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("products", "0002_alter_category_options"),
        ("orders", "0001_initial"),
    ]
    operations = [migrations.RunPython(forwards, backwards)]
