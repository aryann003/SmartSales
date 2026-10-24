import pytest
from django.db import connection

from analytics import sqlviews


@pytest.mark.django_db
class TestSqlViews:
    def test_migrations_create_every_view_the_api_reads(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT viewname FROM pg_views WHERE viewname LIKE 'vw_%'")
            existing = {row[0] for row in cursor.fetchall()}
        assert set(sqlviews.API_VIEWS) <= existing

    def test_statement_extraction_ignores_exploratory_queries(self):
        names = [name for name, _ in sqlviews.view_statements()]
        assert len(names) == len(set(names)) == 12
        assert names.index("vw_rfm_segments") < names.index("vw_winback_candidates")  # dependency order
        assert names.index("vw_daily_sales") < names.index("vw_sales_anomaly")

    def test_refresh_is_repeatable(self):
        assert len(sqlviews.create_views(connection)) == 12
        assert len(sqlviews.create_views(connection)) == 12


@pytest.mark.django_db
class TestAnalyticsEndpoints:
    def test_revenue_matches_orders(self, client_for, sample_data):
        rows = client_for("analyst").get("/api/analytics/revenue/").data
        by_day = {str(r["sale_date"]): float(r["total_revenue"]) for r in rows}
        assert by_day == {"2026-06-01": 20.0, "2026-06-02": 40.0, "2026-06-03": 60.0}
        assert [r["sale_date"] for r in rows] == sorted((r["sale_date"] for r in rows), reverse=True)

    def test_order_counts(self, client_for, sample_data):
        rows = client_for("analyst").get("/api/analytics/orders/").data
        assert all(r["total_orders"] == 1 for r in rows)

    def test_customer_metrics(self, client_for, sample_data):
        rows = {r["customer_name"]: r for r in client_for("manager").get("/api/analytics/customers/").data}
        assert float(rows["Asha"]["total_revenue"]) == 60.0 and rows["Asha"]["total_orders"] == 2
        assert float(rows["Ravi"]["total_revenue"]) == 60.0
        assert rows["Asha"]["customer_tier"] == "Standard"

    def test_product_analytics(self, client_for, sample_data):
        rows = {r["product_name"]: r for r in client_for("manager").get("/api/analytics/products/").data}
        assert float(rows["Lamp"]["total_revenue"]) == 90.0 and float(rows["Mug"]["total_revenue"]) == 30.0
        assert float(rows["Lamp"]["total_returned"]) == 1.0

    def test_rfm_and_winback_return_lists(self, client_for, sample_data):
        client = client_for("analyst")
        rfm = client.get("/api/analytics/rfm/")
        assert rfm.status_code == 200 and len(rfm.data) == 2
        assert client.get("/api/analytics/winback-candidates/").status_code == 200

    def test_anomaly_view_flags_nothing_on_a_rising_trend(self, client_for, sample_data):
        rows = client_for("analyst").get("/api/analytics/anomalies/").data
        assert all((r["pct_drop"] is None) or float(r["pct_drop"]) <= 0 for r in rows)

    def test_missing_views_give_a_clear_503(self, client_for, sample_data):
        with connection.cursor() as cursor:
            cursor.execute("DROP VIEW vw_daily_sales CASCADE")
        resp = client_for("analyst").get("/api/analytics/revenue/")
        assert resp.status_code == 503 and "migrate" in resp.data["detail"]
