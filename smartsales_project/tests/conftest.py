import datetime as dt
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient

from customers.models import Customer
from orders.models import Order, OrderItem, Return
from products.models import Category, Product

ROLES = ["admin", "manager", "analyst", "salesperson"]


@pytest.fixture(autouse=True)
def _isolate_throttles():
    cache.clear()


@pytest.fixture
def make_user(db):
    def _make(role="salesperson", username=None, password="StrongPass123!"):
        user = User.objects.create_user(username=username or f"{role}_user", password=password)
        user.profile.role = role
        user.profile.save()
        return user

    return _make


@pytest.fixture
def client_for(make_user):
    def _client(role):
        client = APIClient()
        client.force_authenticate(user=make_user(role))
        return client

    return _client


@pytest.fixture
def anon():
    return APIClient()


@pytest.fixture
def sample_data(db):
    """Two customers, two products, three orders over three days, one return."""
    category = Category.objects.create(name="Gifts")
    mug = Product.objects.create(name="Mug", category=category, price=Decimal("10.00"), cost=Decimal("6.00"), stock=50)
    lamp = Product.objects.create(name="Lamp", category=category, price=Decimal("30.00"), cost=Decimal("18.00"), stock=20)
    asha = Customer.objects.create(name="Asha", email="asha@example.com", country="India", signup_date=dt.date(2026, 1, 1))
    ravi = Customer.objects.create(name="Ravi", email="ravi@example.com", country="India", signup_date=dt.date(2026, 1, 2))

    def order(customer, day, lines):
        total = sum(q * p for _, q, p in lines)
        o = Order.objects.create(customer=customer, order_date=day, status="completed", total_amount=total)
        for product, qty, price in lines:
            OrderItem.objects.create(order=o, product=product, quantity=qty, unit_price=price)
        return o

    d1, d2, d3 = dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 6, 3)
    o1 = order(asha, d1, [(mug, 2, Decimal("10.00"))])  # 20
    o2 = order(asha, d2, [(mug, 1, Decimal("10.00")), (lamp, 1, Decimal("30.00"))])  # 40
    o3 = order(ravi, d3, [(lamp, 2, Decimal("30.00"))])  # 60
    Return.objects.create(order=o3, product=lamp, quantity=1, reason="Damaged", return_date=d3)
    return {"category": category, "mug": mug, "lamp": lamp, "asha": asha, "ravi": ravi,
            "orders": [o1, o2, o3], "days": (d1, d2, d3)}
