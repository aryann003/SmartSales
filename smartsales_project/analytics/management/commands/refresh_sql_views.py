from django.core.management.base import BaseCommand
from django.db import connection

from analytics import sqlviews


class Command(BaseCommand):
    help = "Drop and recreate the analytics SQL views from the files in sql/."

    def handle(self, *args, **options):
        created = sqlviews.create_views(connection)
        if not created:
            self.stdout.write(self.style.WARNING("Skipped: SQL views require PostgreSQL."))
            return
        self.stdout.write(self.style.SUCCESS(f"Recreated {len(created)} views: {', '.join(created)}"))
