import datetime as dt
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from customers.models import Customer
from orders.models import Order, OrderItem


@pytest.mark.django_db
class TestCustomersApi:
    def test_create_and_list(self, client_for):
        client = client_for("salesperson")
        resp = client.post("/api/customers/", {"name": "Zed", "email": "z@example.com", "country": "UK",
                                                "signup_date": "2026-02-01"}, format="json")
        assert resp.status_code == 201
        assert client.get("/api/customers/").data["count"] == 1

    def test_duplicate_email_rejected(self, client_for, sample_data):
        resp = client_for("manager").post("/api/customers/", {"name": "Dup", "email": "asha@example.com",
                                          "country": "UK", "signup_date": "2026-02-01"}, format="json")
        assert resp.status_code == 400 and "email" in resp.data

    def test_invalid_email_rejected(self, client_for):
        resp = client_for("manager").post("/api/customers/", {"name": "X", "email": "nope", "country": "UK",
                                          "signup_date": "2026-02-01"}, format="json")
        assert resp.status_code == 400

    def test_listing_is_paginated_and_ordered(self, client_for):
        Customer.objects.bulk_create([Customer(name=f"C{i}", email=f"c{i}@x.com", country="IN",
                                               signup_date=dt.date(2026, 1, 1)) for i in range(25)])
        data = client_for("manager").get("/api/customers/").data
        assert data["count"] == 25 and len(data["results"]) == 20 and data["next"]
        ids = [c["id"] for c in data["results"]]
        assert ids == sorted(ids)


@pytest.mark.django_db
class TestProductsApi:
    def test_negative_price_rejected(self, client_for, sample_data):
        resp = client_for("manager").post("/api/products/", {"name": "Bad", "category": sample_data["category"].id,
                                          "price": "-1", "cost": "1", "stock": 1}, format="json")
        assert resp.status_code == 400

    def test_create_product(self, client_for, sample_data):
        resp = client_for("manager").post("/api/products/", {"name": "Pen", "category": sample_data["category"].id,
                                          "price": "2.00", "cost": "1.00", "stock": 10}, format="json")
        assert resp.status_code == 201


@pytest.mark.django_db
class TestOrdersApi:
    def test_orders_include_nested_items(self, client_for, sample_data):
        results = client_for("manager").get("/api/orders/").data["results"]
        assert len(results) == 3 and all(len(o["items"]) >= 1 for o in results)
        assert results[0]["order_date"] >= results[-1]["order_date"]  # newest first

    def test_order_list_query_count_does_not_grow_with_orders(self, client_for, sample_data):
        """Items are prefetched: one query for orders, one for all their items."""
        client = client_for("manager")
        customer, product = sample_data["asha"], sample_data["mug"]
        for i in range(15):
            o = Order.objects.create(customer=customer, order_date=dt.date(2026, 5, 1), total_amount=10)
            OrderItem.objects.create(order=o, product=product, quantity=1, unit_price=10)
        with CaptureQueriesContext(connection) as ctx:
            assert client.get("/api/orders/").status_code == 200
        assert len(ctx.captured_queries) <= 3  # count + orders + prefetched items

    @pytest.mark.parametrize("payload_change", [{"total_amount": "-5"}, {"order_date": "not-a-date"}, {"status": "shipped"}])
    def test_invalid_orders_rejected(self, client_for, sample_data, payload_change):
        payload = {"customer": sample_data["asha"].id, "order_date": "2026-06-04", "status": "pending",
                   "total_amount": "10.00", **payload_change}
        assert client_for("manager").post("/api/orders/", payload, format="json").status_code == 400

    def test_order_item_quantity_must_be_positive(self, client_for, sample_data):
        payload = {"order": sample_data["orders"][0].id, "product": sample_data["mug"].id, "quantity": 0, "unit_price": "1"}
        assert client_for("manager").post("/api/order-items/", payload, format="json").status_code == 400

    def test_return_quantity_must_be_positive(self, client_for, sample_data):
        payload = {"order": sample_data["orders"][2].id, "product": sample_data["lamp"].id, "quantity": 0,
                   "return_date": "2026-06-04"}
        assert client_for("manager").post("/api/returns/", payload, format="json").status_code == 400

    def test_protected_foreign_keys_block_deletes(self, client_for, sample_data):
        """Customers with orders cannot be deleted (on_delete=PROTECT)."""
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            sample_data["asha"].delete()


@pytest.mark.django_db
class TestDocs:
    def test_openapi_schema_and_swagger_are_served(self, anon):
        schema = anon.get("/api/schema/")
        assert schema.status_code == 200 and b"SmartSales API" in schema.content
        assert anon.get("/api/docs/").status_code == 200

    def test_root_redirects_to_dashboard(self, anon):
        assert anon.get("/").status_code == 302
