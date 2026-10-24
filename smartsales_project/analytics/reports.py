"""Daily sales report: build, format, email, and audit-log it."""
import datetime as dt
import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError, connection
from django.db.models import DecimalField, ExpressionWrapper, F, Max, Sum

from core.automation import record
from orders.models import OrderItem, Return

logger = logging.getLogger("smartsales.reports")

LINE_REVENUE = ExpressionWrapper(
    F("quantity") * F("unit_price"), output_field=DecimalField(max_digits=16, decimal_places=2)
)
ANOMALY_DROP_PCT = 30


def _revenue_and_orders(day):
    items = OrderItem.objects.filter(order__order_date=day)
    revenue = items.aggregate(total=Sum(LINE_REVENUE))["total"] or Decimal("0")
    orders = items.values("order_id").distinct().count()
    return revenue, orders


def _anomaly_pct_drop(day):
    """Percent drop versus the trailing 7-day average, from the SQL view (or None)."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pct_drop FROM vw_sales_anomaly WHERE sale_date = %s", [day])
            row = cursor.fetchone()
    except DatabaseError:
        return None
    return float(row[0]) if row and row[0] is not None else None


def build_daily_report(report_date=None):
    """Summarise one day. Defaults to the most recent day that has orders."""
    if report_date is None:
        from orders.models import Order

        report_date = Order.objects.aggregate(d=Max("order_date"))["d"]
    if report_date is None:
        return {"report_date": None, "revenue": 0.0, "orders": 0, "has_data": False}

    revenue, orders = _revenue_and_orders(report_date)
    prev_revenue, _ = _revenue_and_orders(report_date - dt.timedelta(days=1))
    change = None
    if prev_revenue:
        change = round(float((revenue - prev_revenue) / prev_revenue * 100), 2)

    top = (
        OrderItem.objects.filter(order__order_date=report_date)
        .values("product__name")
        .annotate(revenue=Sum(LINE_REVENUE))
        .order_by("-revenue")[:5]
    )
    pct_drop = _anomaly_pct_drop(report_date)
    return {
        "report_date": report_date.isoformat(),
        "has_data": orders > 0,
        "revenue": float(revenue),
        "orders": orders,
        "avg_order_value": round(float(revenue) / orders, 2) if orders else 0.0,
        "change_vs_previous_day_pct": change,
        "returns": Return.objects.filter(return_date=report_date).count(),
        "top_products": [{"name": t["product__name"], "revenue": float(t["revenue"])} for t in top],
        "anomaly": bool(pct_drop is not None and pct_drop > ANOMALY_DROP_PCT),
        "pct_drop_vs_7day_avg": pct_drop,
    }


def format_report(report):
    if not report["has_data"]:
        return "No sales data available."
    lines = [
        f"SmartSales daily report for {report['report_date']}",
        "",
        f"Revenue:          {report['revenue']:,.2f}",
        f"Orders:           {report['orders']}",
        f"Avg order value:  {report['avg_order_value']:,.2f}",
        f"Returns:          {report['returns']}",
    ]
    if report["change_vs_previous_day_pct"] is not None:
        lines.append(f"Vs previous day:  {report['change_vs_previous_day_pct']:+.2f}%")
    if report["anomaly"]:
        lines.append(f"ALERT: revenue is {report['pct_drop_vs_7day_avg']:.1f}% below the 7-day average")
    if report["top_products"]:
        lines += ["", "Top products:"]
        lines += [f"  {i}. {p['name']} ({p['revenue']:,.2f})" for i, p in enumerate(report["top_products"], 1)]
    return "\n".join(lines)


def send_daily_report(report_date=None, recipients=None):
    """Build the report, email it if recipients are configured, and log the run."""
    recipients = list(settings.REPORT_RECIPIENTS if recipients is None else recipients)
    report = build_daily_report(report_date)
    report["emailed_to"] = []
    try:
        if recipients and report["has_data"]:
            send_mail(
                subject=f"SmartSales daily report: {report['report_date']}",
                message=format_report(report),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
            )
            report["emailed_to"] = recipients
        record("daily sales report", "report.daily", "SUCCESS",
               f"{report['report_date']}: revenue {report['revenue']:.2f}, {report['orders']} orders, "
               f"emailed to {len(report['emailed_to'])} recipient(s)")
    except Exception as exc:  # report generation must never crash the caller silently
        record("daily sales report", "report.daily", "FAILED", f"{type(exc).__name__}: {exc}")
        logger.exception("Daily report failed")
        raise
    return report
