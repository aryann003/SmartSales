from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import connection

from core.permissions import IsManager, IsAnalyst
def run_query(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]



class RevenueAnalyticsView(APIView):
    permission_classes  = [IsManager | IsAnalyst]
    def get(self, request):
        data = run_query("SELECT * FROM vw_daily_sales ORDER BY sale_date DESC LIMIT 30")
        return Response(data)


class OrdersAnalyticsView(APIView):
    permission_classes = [IsManager | IsAnalyst]  # TEMPORARY

    def get(self, request):
        data = run_query("""
            SELECT sale_date, total_orders 
            FROM vw_daily_sales 
            ORDER BY sale_date DESC 
            LIMIT 30
        """)
        return Response(data)


class ProductsAnalyticsView(APIView):
    permission_classes = [IsManager | IsAnalyst]  # TEMPORARY

    def get(self, request):
        data = run_query("""
            SELECT * FROM vw_product_analytics 
            ORDER BY total_revenue DESC 
            LIMIT 50
        """)
        return Response(data)


class CustomersAnalyticsView(APIView):
    permission_classes = [IsManager | IsAnalyst]  # TEMPORARY

    def get(self, request):
        data = run_query("""
            SELECT * FROM vw_customer_metrics 
            ORDER BY total_revenue DESC 
            LIMIT 50
        """)
        return Response(data)


class RFMAnalyticsView(APIView):
    permission_classes = [IsManager | IsAnalyst]  # TEMPORARY

    def get(self, request):
        data = run_query("SELECT * FROM vw_rfm_segments ORDER BY monetary DESC LIMIT 50")
        return Response(data)

class SalesAnomalyView(APIView):
    permission_classes = [IsManager | IsAnalyst]

    def get(self, request):
        data = run_query("SELECT * FROM vw_sales_anomaly ORDER BY sale_date DESC LIMIT 50")
        return Response(data)



class WinBackCandidatesView(APIView):
    permission_classes  = [IsManager| IsAnalyst]

    def get (self,request):
        data = run_query("SELECT * FROM vw_winback_candidates")
        return Response(data)