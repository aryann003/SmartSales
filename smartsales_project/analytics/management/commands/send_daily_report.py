import datetime as dt

from django.core.management.base import BaseCommand

from analytics.reports import format_report, send_daily_report


class Command(BaseCommand):
    help = "Build the daily sales report, email it to REPORT_RECIPIENTS, and log the run."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD (default: latest day with orders)")

    def handle(self, *args, **options):
        day = dt.date.fromisoformat(options["date"]) if options["date"] else None
        report = send_daily_report(day)
        self.stdout.write(format_report(report))
        if report["emailed_to"]:
            self.stdout.write(self.style.SUCCESS(f"Emailed to: {', '.join(report['emailed_to'])}"))
