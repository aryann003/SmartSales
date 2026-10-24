"""Role-based access: who may read and write each resource."""
import pytest

READ_ENDPOINTS = ["/api/customers/", "/api/products/", "/api/categories/", "/api/orders/",
                  "/api/order-items/", "/api/returns/"]
ANALYTICS = ["revenue", "orders", "products", "customers", "rfm", "anomalies", "winback-candidates"]


@pytest.mark.django_db
class TestAuthentication:
    @pytest.mark.parametrize("url", READ_ENDPOINTS + [f"/api/analytics/{a}/" for a in ANALYTICS])
    def test_anonymous_is_rejected(self, anon, url):
        assert anon.get(url).status_code == 401

    def test_login_returns_tokens(self, anon, make_user):
        make_user("manager", username="mia")
        resp = anon.post("/api/token/", {"username": "mia", "password": "StrongPass123!"}, format="json")
        assert resp.status_code == 200 and {"access", "refresh"} <= set(resp.data)

    def test_login_is_rate_limited(self, anon, make_user):
        make_user("manager", username="mia")
        codes = [anon.post("/api/token/", {"username": "mia", "password": "bad"}, format="json").status_code
                 for _ in range(11)]
        assert codes[:10] == [401] * 10 and codes[10] == 429


@pytest.mark.django_db
class TestReadAccess:
    @pytest.mark.parametrize("role", ["admin", "manager", "analyst", "salesperson"])
    @pytest.mark.parametrize("url", READ_ENDPOINTS)
    def test_every_role_can_read(self, client_for, role, url):
        assert client_for(role).get(url).status_code == 200

    def test_categories_serialize_when_data_exists(self, client_for, sample_data):
        """Regression: `class Mets:` (typo for Meta) crashed as soon as a category existed."""
        resp = client_for("salesperson").get("/api/categories/")
        assert resp.status_code == 200 and resp.data["results"][0]["name"] == "Gifts"

    def test_salesperson_can_list_customers(self, client_for):
        """Regression: a typo (`profile.rolw`) made this endpoint crash for everyone."""
        assert client_for("salesperson").get("/api/customers/").status_code == 200


CUSTOMER = {"name": "New", "email": "new@example.com", "country": "UK", "signup_date": "2026-01-01"}


@pytest.mark.django_db
class TestWriteAccess:
    @pytest.mark.parametrize("role,expected", [("admin", 201), ("manager", 201), ("salesperson", 201), ("analyst", 403)])
    def test_create_customer(self, client_for, role, expected):
        assert client_for(role).post("/api/customers/", CUSTOMER, format="json").status_code == expected

    @pytest.mark.parametrize("role,expected", [("admin", 201), ("manager", 201), ("salesperson", 403), ("analyst", 403)])
    def test_create_category(self, client_for, role, expected):
        assert client_for(role).post("/api/categories/", {"name": f"C-{role}"}, format="json").status_code == expected

    @pytest.mark.parametrize("role,expected", [("manager", 201), ("salesperson", 201), ("analyst", 403)])
    def test_create_order(self, client_for, sample_data, role, expected):
        payload = {"customer": sample_data["asha"].id, "order_date": "2026-06-04", "status": "pending", "total_amount": "10.00"}
        assert client_for(role).post("/api/orders/", payload, format="json").status_code == expected

    @pytest.mark.parametrize("role,expected", [("manager", 204), ("salesperson", 204), ("analyst", 403)])
    def test_delete_return(self, client_for, sample_data, role, expected):
        from orders.models import Return
        ret = Return.objects.get()
        assert client_for(role).delete(f"/api/returns/{ret.id}/").status_code == expected

    def test_salesperson_cannot_change_prices(self, client_for, sample_data):
        resp = client_for("salesperson").patch(f"/api/products/{sample_data['mug'].id}/", {"price": "1.00"}, format="json")
        assert resp.status_code == 403
        sample_data["mug"].refresh_from_db()
        assert str(sample_data["mug"].price) == "10.00"

    def test_manager_can_change_prices(self, client_for, sample_data):
        resp = client_for("manager").patch(f"/api/products/{sample_data['mug'].id}/", {"price": "12.50"}, format="json")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestAnalyticsAccess:
    @pytest.mark.parametrize("role,expected", [("admin", 200), ("manager", 200), ("analyst", 200), ("salesperson", 403)])
    @pytest.mark.parametrize("name", ANALYTICS)
    def test_analytics_roles(self, client_for, sample_data, role, expected, name):
        assert client_for(role).get(f"/api/analytics/{name}/").status_code == expected

    def test_analytics_are_read_only(self, client_for):
        assert client_for("manager").post("/api/analytics/revenue/", {}, format="json").status_code == 405


@pytest.mark.django_db
class TestProfiles:
    def test_new_users_get_least_privileged_profile(self, db):
        from django.contrib.auth.models import User
        assert User.objects.create_user("plain", password="x").profile.role == "salesperson"

    def test_superusers_become_admins(self, db):
        from django.contrib.auth.models import User
        assert User.objects.create_superuser("root", password="x").profile.role == "admin"
