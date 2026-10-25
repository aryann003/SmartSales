import datetime as dt
from decimal import Decimal
from unittest import mock

import pytest
from django.test import Client

from customers.models import Customer
from orders.models import Order, OrderItem, Return


@pytest.fixture
def web(make_user):
    user = make_user("salesperson", username="sam")
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestWebUi:
    @pytest.mark.parametrize("url", ["/dashboard/", "/customers/", "/products/", "/orders/", "/returns/",
                                     "/customers/add/", "/products/add/", "/orders/add/", "/returns/add/"])
    def test_login_required(self, url):
        resp = Client().get(url)
        assert resp.status_code == 302 and "/login/" in resp["Location"]

    @pytest.mark.parametrize("url", ["/dashboard/", "/customers/", "/products/", "/orders/", "/returns/",
                                     "/customers/add/", "/products/add/", "/orders/add/", "/returns/add/"])
    def test_pages_render_when_signed_in(self, web, sample_data, url):
        assert web.get(url).status_code == 200

    def test_login_flow(self, make_user):
        make_user("manager", username="mia")
        client = Client()
        resp = client.post("/login/", {"username": "mia", "password": "StrongPass123!"})
        assert resp.status_code == 302 and resp["Location"].endswith("/dashboard/")

    def test_logout_requires_post(self, web):
        assert web.get("/logout/").status_code == 405
        assert web.post("/logout/").status_code == 302

    def test_add_customer(self, web):
        resp = web.post("/customers/add/", {"name": "Neha", "email": "n@example.com", "country": "IN",
                                            "signup_date": "2026-03-01"})
        assert resp.status_code == 302 and Customer.objects.filter(email="n@example.com").exists()

    def test_customer_list_paginates_and_keeps_requested_page_size(self, web):
        Customer.objects.bulk_create([
            Customer(name=f"Customer {index}", email=f"customer{index}@example.com", country="IN",
                     signup_date=dt.date(2026, 1, 1))
            for index in range(30)
        ])
        response = web.get("/customers/?page=2&per_page=10")
        assert response.status_code == 200
        assert len(response.context["customers"]) == 10
        assert response.context["page_obj"].number == 2
        assert b"Showing 11" in response.content and b"of 30" in response.content

    def test_product_list_paginates(self, web, sample_data):
        from products.models import Product

        Product.objects.bulk_create([
            Product(name=f"Product {index}", category=sample_data["category"], price=1, cost=1, stock=1)
            for index in range(26)
        ])
        response = web.get("/products/?page=2&per_page=10")
        assert response.status_code == 200
        assert len(response.context["products"]) == 10
        assert response.context["page_obj"].number == 2

    def test_order_list_paginates(self, web, sample_data):
        Order.objects.bulk_create([
            Order(customer=sample_data["asha"], order_date=dt.date(2026, 6, 4), status="completed",
                  total_amount=Decimal("10.00"))
            for _ in range(26)
        ])
        response = web.get("/orders/?page=2&per_page=10")
        assert response.status_code == 200
        assert len(response.context["orders"]) == 10
        assert response.context["page_obj"].number == 2

    def test_return_page_paginates(self, web, sample_data):
        Return.objects.bulk_create([
            Return(order=sample_data["orders"][0], product=sample_data["mug"], quantity=1,
                   reason="Test", return_date=dt.date(2026, 6, 4))
            for _ in range(26)
        ])
        response = web.get("/returns/?page=2&per_page=10")
        assert response.status_code == 200
        assert len(response.context["returns"]) == 10
        assert response.context["page_obj"].number == 2

    def test_add_return(self, web, sample_data):
        response = web.post("/returns/add/", {
            "order": sample_data["orders"][0].id,
            "product": sample_data["mug"].id,
            "quantity": 1,
            "reason": "Customer request",
            "return_date": "2026-06-04",
        })
        assert response.status_code == 302 and response["Location"].endswith("/returns/")
        assert Return.objects.filter(
            order=sample_data["orders"][0],
            product=sample_data["mug"],
            quantity=1,
            reason="Customer request",
        ).exists()

    def test_analyst_cannot_add_return(self, make_user, sample_data):
        client = Client()
        client.force_login(make_user("analyst", username="analyst"))
        response = client.post("/returns/add/", {
            "order": sample_data["orders"][0].id,
            "product": sample_data["mug"].id,
            "quantity": 1,
            "reason": "Customer request",
            "return_date": "2026-06-04",
        })
        assert response.status_code == 403


@pytest.mark.django_db
class TestOrderCreation:
    def form(self, data):
        return {"customer": data["asha"].id, "order_date": "2026-06-10", "status": "pending",
                "product": data["mug"].id, "quantity": 3, "unit_price": "10.00"}

    def test_total_is_computed_from_the_item(self, web, sample_data):
        before = Order.objects.count()
        assert web.post("/orders/add/", self.form(sample_data)).status_code == 302
        order = Order.objects.order_by("-id").first()
        assert Order.objects.count() == before + 1 and order.total_amount == 30
        assert order.items.get().quantity == 3

    def test_invalid_item_creates_no_order(self, web, sample_data):
        before = Order.objects.count()
        bad = {**self.form(sample_data), "quantity": ""}
        assert web.post("/orders/add/", bad).status_code == 200
        assert Order.objects.count() == before

    def test_order_and_item_are_saved_atomically(self, web, sample_data):
        """If saving the item fails, the order must be rolled back too."""
        before = Order.objects.count()
        with mock.patch.object(OrderItem, "save", side_effect=RuntimeError("boom")):
            assert web.post("/orders/add/", self.form(sample_data)).status_code == 500
        assert Order.objects.count() == before
