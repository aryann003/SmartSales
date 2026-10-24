from django.db import DatabaseError, connection
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import AutomationLog
from core.permissions import HasAutomationKey, IsAnalyst, IsManager

from .reports import send_daily_report
from .serializers import AutomationLogInputSerializer, DailyReportInputSerializer


class AnalyticsUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Analytics views are unavailable. Run `python manage.py migrate` on PostgreSQL."
    default_code = "analytics_unavailable"


def run_query(sql, params=None):
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except DatabaseError as exc:
        raise AnalyticsUnavailable() from exc


class ViewBackedAnalytics(APIView):
    """Read-only endpoint backed by a SQL view. Managers, analysts and admins only."""

    permission_classes = [IsManager | IsAnalyst]
    sql = ""

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response(run_query(self.sql))


class RevenueAnalyticsView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_daily_sales ORDER BY sale_date DESC LIMIT 30"


class OrdersAnalyticsView(ViewBackedAnalytics):
    sql = "SELECT sale_date, total_orders FROM vw_daily_sales ORDER BY sale_date DESC LIMIT 30"


class ProductsAnalyticsView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_product_analytics ORDER BY total_revenue DESC LIMIT 50"


class CustomersAnalyticsView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_customer_metrics ORDER BY total_revenue DESC LIMIT 50"


class RFMAnalyticsView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_rfm_segments ORDER BY monetary DESC LIMIT 50"


class SalesAnomalyView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_sales_anomaly ORDER BY sale_date DESC LIMIT 50"


class WinBackCandidatesView(ViewBackedAnalytics):
    sql = "SELECT * FROM vw_winback_candidates"


class LogAutomationView(APIView):
    """Workflows (n8n, scheduled jobs) record their runs here.

    Protected by the shared ``X-Automation-Token`` header (``AUTOMATION_API_KEY``).
    """

    permission_classes = [HasAutomationKey]

    @extend_schema(request=AutomationLogInputSerializer, responses={201: OpenApiTypes.OBJECT})
    def post(self, request):
        serializer = AutomationLogInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        log = AutomationLog.objects.create(**serializer.validated_data)
        return Response({"status": "logged", "id": log.id}, status=status.HTTP_201_CREATED)


class DailyReportView(APIView):
    """Build (and email, if recipients are configured) the daily sales report.

    Meant to be called on a schedule by a trusted caller such as a GitHub Actions
    cron job or n8n, using the ``X-Automation-Token`` header.
    """

    permission_classes = [HasAutomationKey]

    @extend_schema(request=DailyReportInputSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        serializer = DailyReportInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = send_daily_report(serializer.validated_data.get("date"))
        return Response(report)
