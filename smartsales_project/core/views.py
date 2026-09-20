from django.shortcuts import render

from django.shortcuts import render
from customers.models import Customer
from orders.models import Order
from products.models import Product
from orders.models import Order, Return
def dashboard(request):
    context = {
        'total_customers': Customer.objects.count(),
        'total_orders': Order.objects.count(),
        'total_products': Product.objects.count(),
        'total_returns' : Return.objects.count()

    }
    return render(request, 'dashboard.html', context)