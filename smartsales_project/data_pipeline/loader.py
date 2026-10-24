"""Load cleaned retail data into the Django models.

Run through ``python manage.py import_retail_data``. The whole load is a single
transaction, so a failure leaves the database untouched, and re-running is
refused unless ``replace=True`` so data is never silently duplicated.
"""
import logging

from django.db import transaction

from customers.models import Customer
from orders.models import Order, OrderItem, Return
from products.models import Category, Product

from .cleaning import clean_data
from .ingestion import load_raw_data
from .validation import validate_data

logger = logging.getLogger("smartsales.pipeline")

BATCH_SIZE = 5000


class AlreadyLoadedError(RuntimeError):
    pass


def delete_existing_data():
    """Remove imported data in dependency order (the FKs are PROTECT)."""
    for model in (Return, OrderItem, Order, Product, Customer):
        model.objects.all().delete()


@transaction.atomic
def load_data(df, replace=False):
    """Insert customers, products, orders, items and returns. Returns a stats dict."""
    if Order.objects.exists():
        if not replace:
            raise AlreadyLoadedError("Orders already exist. Use replace=True to reload from scratch.")
        delete_existing_data()

    default_category, _ = Category.objects.get_or_create(name="Imported")

    # ---------- customers
    cust_rows = df.drop_duplicates(subset=["customer_ref"])
    email_for = {int(r.customer_ref): f"customer{int(r.customer_ref)}@smartsales-import.com"
                 for r in cust_rows.itertuples()}
    Customer.objects.bulk_create(
        [Customer(email=email_for[int(r.customer_ref)], name=f"Customer {int(r.customer_ref)}",
                  country=r.country, signup_date=r.order_date.date())
         for r in cust_rows.itertuples()],
        batch_size=BATCH_SIZE, ignore_conflicts=True,
    )
    ref_for_email = {email: ref for ref, email in email_for.items()}
    customer_id_map = {ref_for_email[c["email"]]: c["id"]
                       for c in Customer.objects.filter(email__in=list(ref_for_email)).values("id", "email")}

    # ---------- products
    prod_rows = df.drop_duplicates(subset=["product_code"])
    products = [Product(name=r.product_name[:200], category=default_category,
                        price=abs(r.unit_price), cost=abs(r.unit_price) * 0.6, stock=100)
                for r in prod_rows.itertuples()]
    Product.objects.bulk_create(products, batch_size=BATCH_SIZE)
    product_id_map = {code: p.id for code, p in zip(prod_rows["product_code"], products)}

    # ---------- orders
    order_totals = df[~df["is_return"]].groupby("order_ref")["revenue"].sum()
    order_rows = df.drop_duplicates(subset=["order_ref"])
    orders = [Order(customer_id=customer_id_map[int(r.customer_ref)], order_date=r.order_date.date(),
                    status="completed", total_amount=round(float(order_totals.get(r.order_ref, 0)), 2))
              for r in order_rows.itertuples()]
    Order.objects.bulk_create(orders, batch_size=BATCH_SIZE)
    order_id_map = {ref: o.id for ref, o in zip(order_rows["order_ref"], orders)}

    # ---------- order items and returns
    items, returns = [], []
    for r in df.itertuples():
        order_id, product_id = order_id_map[r.order_ref], product_id_map[r.product_code]
        if r.is_return:
            returns.append(Return(order_id=order_id, product_id=product_id, quantity=abs(int(r.quantity)),
                                  reason="Imported from historical data", return_date=r.order_date.date()))
        else:
            items.append(OrderItem(order_id=order_id, product_id=product_id,
                                   quantity=int(r.quantity), unit_price=r.unit_price))
    OrderItem.objects.bulk_create(items, batch_size=BATCH_SIZE)
    Return.objects.bulk_create(returns, batch_size=BATCH_SIZE)

    stats = {"customers": len(cust_rows), "products": len(products), "orders": len(orders),
             "order_items": len(items), "returns": len(returns)}
    logger.info("Loaded %s", stats)
    return stats


def run_pipeline(filepath, limit=None, replace=False):
    """ingest -> clean -> validate -> load. Returns a stats dict."""
    raw = load_raw_data(filepath, limit=limit)
    cleaned = validate_data(clean_data(raw))
    stats = load_data(cleaned, replace=replace)
    stats.update(raw_rows=len(raw), clean_rows=len(cleaned), dropped_rows=len(raw) - len(cleaned))
    return stats
