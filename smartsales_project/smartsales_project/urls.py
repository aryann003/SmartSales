from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.generic import RedirectView
from core.auth_views import ThrottledTokenObtainPairView

from core.views import dashboard
from customers.views import CustomerViewSet, customer_list, customer_add
from products.views import CategoryViewSet, ProductViewSet, product_list, product_add
from orders.views import OrderViewSet, OrderItemViewSet, ReturnViewSet, order_list, order_add, return_list, return_add
from analytics.views import (
    RevenueAnalyticsView, OrdersAnalyticsView, 
    ProductsAnalyticsView, CustomersAnalyticsView, RFMAnalyticsView, SalesAnomalyView, WinBackCandidatesView, LogAutomationView, DailyReportView
)
from django.contrib.auth import views as auth_views

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'returns', ReturnViewSet)

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='dashboard', permanent=False)),
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/', include(router.urls)),
    path('api/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('dashboard/', dashboard, name='dashboard'),

    path('customers/', customer_list, name='customer_list'),
    path('customers/add/', customer_add, name='customer_add'),

    path('products/', product_list, name='product_list'),
    path('products/add/', product_add, name='product_add'),

    path('orders/', order_list, name='order_list'),
    path('orders/add/', order_add, name='order_add'),

    path('returns/', return_list, name='return_list'),
    path('returns/add/', return_add, name='return_add'),

    path('api/analytics/revenue/', RevenueAnalyticsView.as_view(), name='revenue_analytics'),
    path('api/analytics/orders/', OrdersAnalyticsView.as_view(), name='orders_analytics'),
    path('api/analytics/products/', ProductsAnalyticsView.as_view(), name='products_analytics'),
    path('api/analytics/customers/', CustomersAnalyticsView.as_view(), name='customers_analytics'),
    path('api/analytics/rfm/', RFMAnalyticsView.as_view(), name='rfm_analytics'),
    path('api/analytics/anomalies/', SalesAnomalyView.as_view(), name='sales_anomalies'),
    path('api/analytics/winback-candidates/', WinBackCandidatesView.as_view(), name='winback_candidates'),
    path('api/analytics/log/', LogAutomationView.as_view(), name='log_automation'),
    path('api/automation/daily-report/', DailyReportView.as_view(), name='daily_report'),

    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]