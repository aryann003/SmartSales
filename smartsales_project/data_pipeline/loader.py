import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartsales_project.settings')
django.setup()

from customers.models import Customer
from products.models import Product, Category
from orders.models import Order, OrderItem, Return

from .ingestion import load_raw_data
from .cleaning import clean_data
from .validation import validate_data

BATCH_SIZE = 5000


def get_or_create_default_category():
    category, _ = Category.objects.get_or_create(name='Imported')
    return category


def load_data(df):
    default_category = get_or_create_default_category()

    # ---------- 1. CUSTOMERS ----------
    print("Preparing customers...")
    cust_rows = df.drop_duplicates(subset=['customer_ref'])
    customers = [
        Customer(
            email=f"customer{int(r.customer_ref)}@smartsales-import.com",
            name=f"Customer {int(r.customer_ref)}",
            country=r.country,
            signup_date=r.order_date.date(),
        )
        for r in cust_rows.itertuples()
    ]
    Customer.objects.bulk_create(customers, batch_size=BATCH_SIZE, ignore_conflicts=True)
    print(f"Customers ready: {len(customers)}")

    email_to_ref = {
        f"customer{int(r.customer_ref)}@smartsales-import.com": int(r.customer_ref)
        for r in cust_rows.itertuples()
    }
    customer_id_map = {}
    for c in Customer.objects.filter(email__in=list(email_to_ref.keys())).values('id', 'email'):
        customer_id_map[email_to_ref[c['email']]] = c['id']

    # ---------- 2. PRODUCTS ----------
    print("Preparing products...")
    prod_rows = df.drop_duplicates(subset=['product_code'])
    products = [
        Product(
            name=r.product_name[:200],
            category=default_category,
            price=abs(r.unit_price),
            cost=abs(r.unit_price) * 0.6,
            stock=100,
        )
        for r in prod_rows.itertuples()
    ]
    Product.objects.bulk_create(products, batch_size=BATCH_SIZE)
    product_id_map = {code: p.id for code, p in zip(prod_rows['product_code'], products)}
    print(f"Products ready: {len(products)}")

    # ---------- 3. ORDERS ----------
    print("Preparing orders...")
    order_totals = df[~df['is_return']].groupby('order_ref')['revenue'].sum()
    order_rows = df.drop_duplicates(subset=['order_ref'])
    orders = [
        Order(
            customer_id=customer_id_map[int(r.customer_ref)],
            order_date=r.order_date.date(),
            status='completed',
            total_amount=round(order_totals.get(r.order_ref, 0), 2),
        )
        for r in order_rows.itertuples()
    ]
    Order.objects.bulk_create(orders, batch_size=BATCH_SIZE)
    order_id_map = {ref: o.id for ref, o in zip(order_rows['order_ref'], orders)}
    print(f"Orders ready: {len(orders)}")

    # ---------- 4. ORDER ITEMS + RETURNS ----------
    print("Preparing order items and returns...")
    items, returns = [], []
    for r in df.itertuples():
        order_id = order_id_map[r.order_ref]
        product_id = product_id_map[r.product_code]
        if r.is_return:
            returns.append(Return(
                order_id=order_id, product_id=product_id,
                quantity=abs(int(r.quantity)),
                reason='Imported from historical data',
                return_date=r.order_date.date(),
            ))
        else:
            items.append(OrderItem(
                order_id=order_id, product_id=product_id,
                quantity=int(r.quantity), unit_price=r.unit_price,
            ))

    OrderItem.objects.bulk_create(items, batch_size=BATCH_SIZE)
    Return.objects.bulk_create(returns, batch_size=BATCH_SIZE)

    print(f"\nDone. Customers: {len(customers)}, Products: {len(products)}, "
          f"Orders: {len(orders)}, OrderItems: {len(items)}, Returns: {len(returns)}")


if __name__ == '__main__':
    df = load_raw_data()
    df = clean_data(df)
    df = validate_data(df)
    load_data(df)