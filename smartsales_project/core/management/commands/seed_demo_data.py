"""Fill an empty database with realistic, deterministic demo data.

Used for the live demo so it does not depend on the large Kaggle dataset.
Creates catalog, customers, ~90 days of orders (with a deliberate sales dip so the
anomaly view has something to flag), returns, and one demo user per role.
"""
import datetime as dt
import os
import random
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer
from data_pipeline.loader import delete_existing_data
from orders.models import Order, OrderItem, Return
from products.models import Category, Product

CATALOG = {
    "Home & Kitchen": ["Ceramic Mug", "Steel Water Bottle", "Cotton Tea Towel", "Glass Jar Set", "Wooden Cutting Board", "Scented Candle"],
    "Stationery": ["Hardcover Notebook", "Gel Pen Pack", "Desk Organiser", "Sticky Note Set", "Wall Planner", "Pencil Case"],
    "Electronics": ["USB-C Cable", "Wireless Mouse", "Phone Stand", "LED Desk Lamp", "Bluetooth Speaker", "Power Bank"],
    "Gifts": ["Greeting Card Set", "Gift Wrap Roll", "Photo Frame", "Mini Succulent", "Keychain", "Puzzle Box"],
    "Outdoor": ["Picnic Blanket", "Foldable Umbrella", "Camping Lantern", "Sun Hat", "Tote Bag", "Hand Warmer"],
}
FIRST = ["Aarav", "Diya", "Rohan", "Ananya", "Kabir", "Isha", "Vihaan", "Meera", "Arjun", "Sara", "Neil", "Priya", "Dev", "Tara", "Kunal"]
LAST = ["Sharma", "Verma", "Gupta", "Iyer", "Khan", "Patel", "Singh", "Das", "Nair", "Reddy", "Bose", "Mehta"]
COUNTRIES = ["India"] * 6 + ["United Kingdom", "Germany", "France", "Australia", "Singapore"]
DEMO_USERS = [("demo_admin", "admin"), ("demo_manager", "manager"),
              ("demo_analyst", "analyst"), ("demo_salesperson", "salesperson")]


class Command(BaseCommand):
    help = "Create demo catalog, customers, orders, returns and one user per role."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--orders-per-day", type=int, default=25)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--replace", action="store_true", help="Delete existing sales data first")
        parser.add_argument("--if-empty", action="store_true",
                            help="Do nothing (exit 0) when orders already exist; safe to run on every deploy")

    @transaction.atomic
    def handle(self, *args, **opts):
        if Order.objects.exists():
            if opts["if_empty"]:
                self.stdout.write("Orders already exist, skipping demo data.")
                return
            if not opts["replace"]:
                raise CommandError("Orders already exist. Use --replace to reseed.")
            delete_existing_data()
            Category.objects.all().delete()

        rng = random.Random(opts["seed"])
        password = os.environ.get("DEMO_PASSWORD", "DemoPass123!")

        # users, one per role
        for username, role in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.save()
            user.profile.role = role
            user.profile.save()

        # catalog
        products = []
        for category_name, names in CATALOG.items():
            category = Category.objects.create(name=category_name)
            for name in names:
                price = Decimal(rng.randrange(150, 4500)) / 10
                products.append(Product(name=name, category=category, price=price,
                                        cost=(price * Decimal("0.6")).quantize(Decimal("0.01")),
                                        stock=rng.randrange(20, 400)))
        Product.objects.bulk_create(products)
        products = list(Product.objects.all())

        # customers (signed up before the first order)
        today = timezone.now().date()
        start = today - dt.timedelta(days=opts["days"])
        customers = Customer.objects.bulk_create([
            Customer(name=f"{rng.choice(FIRST)} {rng.choice(LAST)}", email=f"customer{i:03d}@demo.example",
                     country=rng.choice(COUNTRIES), signup_date=start - dt.timedelta(days=rng.randrange(1, 300)))
            for i in range(120)
        ])
        customers = list(Customer.objects.all())
        loyal = customers[:25]  # repeat buyers, so RFM and tiers have a signal

        dip_day = today - dt.timedelta(days=4)  # deliberately weak day for anomaly detection
        orders, plan = [], []
        for offset in range(opts["days"], 0, -1):
            day = today - dt.timedelta(days=offset)
            volume = opts["orders_per_day"] * (0.7 if day.weekday() >= 5 else 1.0)
            volume *= 0.3 if day == dip_day else rng.uniform(0.8, 1.2)
            for _ in range(max(1, int(volume))):
                customer = rng.choice(loyal) if rng.random() < 0.45 else rng.choice(customers)
                lines = [(rng.choice(products), rng.randrange(1, 6)) for _ in range(rng.randrange(1, 4))]
                total = sum(p.price * q for p, q in lines)
                status = rng.choices(["completed", "pending", "canceled"], weights=[90, 5, 5])[0]
                orders.append(Order(customer=customer, order_date=day, status=status, total_amount=total))
                plan.append((day, lines))
        orders = Order.objects.bulk_create(orders)

        items, returns = [], []
        for order, (day, lines) in zip(orders, plan):
            for product, qty in lines:
                items.append(OrderItem(order=order, product=product, quantity=qty, unit_price=product.price))
                if rng.random() < 0.03:
                    returns.append(Return(order=order, product=product, quantity=1,
                                          reason=rng.choice(["Damaged", "Wrong item", "Changed mind"]),
                                          return_date=min(day + dt.timedelta(days=rng.randrange(1, 6)), today)))
        OrderItem.objects.bulk_create(items, batch_size=2000)
        Return.objects.bulk_create(returns)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {len(customers)} customers, {len(products)} products, {len(orders)} orders, "
            f"{len(items)} items, {len(returns)} returns, and users: "
            + ", ".join(u for u, _ in DEMO_USERS)))
