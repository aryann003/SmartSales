from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from customers.views import CustomerViewSet, customer_list, customer_add
from products.views import CategoryViewSet, ProductViewSet, product_list, product_add
from orders.views import OrderViewSet, OrderItemViewSet, ReturnViewSet, order_list, order_add, return_list

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
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('customers/', customer_list, name='customer_list'),
    path('customers/add/', customer_add, name='customer_add'),

    path('products/', product_list, name='product_list'),
    path('products/add/', product_add, name='product_add'),

    path('orders/', order_list, name='order_list'),
    path('orders/add/', order_add, name='order_add'),

    path('returns/', return_list, name='return_list'),
]