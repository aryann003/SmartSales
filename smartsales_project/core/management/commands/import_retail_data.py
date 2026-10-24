from django.core.management.base import BaseCommand, CommandError

from data_pipeline.ingestion import DEFAULT_PATH
from data_pipeline.loader import AlreadyLoadedError, run_pipeline
from data_pipeline.validation import DataValidationError


class Command(BaseCommand):
    help = ("Run the retail ETL pipeline (ingest, clean, validate, load) on the "
            "Online Retail II CSV. The whole load is one transaction.")

    def add_arguments(self, parser):
        parser.add_argument("--file", default=DEFAULT_PATH, help=f"CSV path (default: {DEFAULT_PATH})")
        parser.add_argument("--limit", type=int, help="Only read the first N raw rows (for demos or small databases)")
        parser.add_argument("--replace", action="store_true",
                            help="Delete existing customers, products and orders first")

    def handle(self, *args, **opts):
        try:
            stats = run_pipeline(opts["file"], limit=opts["limit"], replace=opts["replace"])
        except FileNotFoundError:
            raise CommandError(f"File not found: {opts['file']} (see the README for the dataset download)")
        except AlreadyLoadedError as exc:
            raise CommandError(str(exc))
        except DataValidationError as exc:
            raise CommandError("Validation failed, nothing was loaded:\n  - " + "\n  - ".join(exc.issues))
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {stats['raw_rows']} raw rows ({stats['dropped_rows']} dropped in cleaning): "
            f"{stats['customers']} customers, {stats['products']} products, {stats['orders']} orders, "
            f"{stats['order_items']} items, {stats['returns']} returns"))
