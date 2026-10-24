import datetime as dt
from unittest import mock

import pytest
from django.test import Client

from customers.models import Customer
from orders.models import Order, OrderItem


@pytest.fixture
def web(make_user):
    user = make_user("salesperson", username="sam")
    client = Client(raise_request_exception=False)
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestWebUi:
    @pytest.mark.parametrize("url", ["/dashboard/", "/customers/", "/products/", "/orders/", "/returns/",
                                     "/customers/add/", "/products/add/", "/orders/add/"])
    def test_login_required(self, url):
        resp = Client().get(url)
        assert resp.status_code == 302 and "/login/" in resp["Location"]

    @pytest.mark.parametrize("url", ["/dashboard/", "/customers/", "/products/", "/orders/", "/returns/",
                                     "/customers/add/", "/products/add/", "/orders/add/"])
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
