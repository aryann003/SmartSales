import pytest
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.db import connection

from customers.models import Customer
from orders.models import Order, OrderItem


@pytest.mark.django_db
class TestSeedDemoData:
    @pytest.fixture
    def seeded(self):
        call_command("seed_demo_data", "--days", "30", "--orders-per-day", "8")

    def test_creates_realistic_data(self, seeded):
        assert Customer.objects.count() == 120 and Order.objects.count() > 100
        assert OrderItem.objects.count() > Order.objects.count()

    def test_creates_one_user_per_role(self, seeded):
        roles = {u.username: u.profile.role for u in User.objects.filter(username__startswith="demo_")}
        assert roles == {"demo_admin": "admin", "demo_manager": "manager",
                         "demo_analyst": "analyst", "demo_salesperson": "salesperson"}

    def test_demo_logins_work_and_roles_are_enforced(self, seeded, anon):
        def token(user):
            return anon.post("/api/token/", {"username": user, "password": "DemoPass123!"}, format="json").data["access"]
        anon.credentials(HTTP_AUTHORIZATION=f"Bearer {token('demo_analyst')}")
        assert anon.get("/api/analytics/rfm/").status_code == 200
        anon.credentials(HTTP_AUTHORIZATION=f"Bearer {token('demo_salesperson')}")
        assert anon.get("/api/analytics/rfm/").status_code == 403

    def test_analytics_views_have_content(self, seeded):
        with connection.cursor() as cursor:
            for view in ("vw_daily_sales", "vw_rfm_segments", "vw_product_analytics", "vw_customer_metrics"):
                cursor.execute(f"SELECT COUNT(*) FROM {view}")
                assert cursor.fetchone()[0] > 0, view

    def test_includes_a_detectable_sales_dip(self, seeded):
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM vw_sales_anomaly WHERE pct_drop > 30")
            assert cursor.fetchone()[0] >= 1

    def test_is_deterministic(self):
        call_command("seed_demo_data", "--days", "10", "--orders-per-day", "5")
        first = list(Order.objects.order_by("id").values_list("customer_id", "total_amount"))
        call_command("seed_demo_data", "--days", "10", "--orders-per-day", "5", "--replace")
        assert len(first) == Order.objects.count()

    def test_if_empty_is_a_safe_noop_on_redeploys(self, seeded, capsys):
        before = Order.objects.count()
        call_command("seed_demo_data", "--if-empty")
        assert Order.objects.count() == before and "skipping" in capsys.readouterr().out

    def test_refuses_to_duplicate_unless_replace(self, seeded):
        with pytest.raises(CommandError, match="already exist"):
            call_command("seed_demo_data")


@pytest.mark.django_db
def test_refresh_sql_views_command(capsys):
    call_command("refresh_sql_views")
    assert "Recreated 12 views" in capsys.readouterr().out


@pytest.mark.django_db
def test_views_can_be_dropped_and_restored():
    from analytics import sqlviews
    sqlviews.drop_views(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM pg_views WHERE viewname LIKE 'vw_%'")
        assert cursor.fetchone()[0] == 0
    sqlviews.create_views(connection)
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM pg_views WHERE viewname LIKE 'vw_%'")
        assert cursor.fetchone()[0] == 12
