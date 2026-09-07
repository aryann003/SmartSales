from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from customers.views import CustomerViewSet
from products.views import CategoryViewSet, ProductViewSet
from orders.views import OrderViewSet, OrderItemViewSet, ReturnViewSet

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'categories', CategoryViewSet)
router.register(r'products', ProductViewSet)
router.register(r'orders', OrderViewSet)
router.register(r'order-items', OrderItemViewSet)
router.register(r'returns', ReturnViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]