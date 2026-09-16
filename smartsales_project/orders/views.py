from django.shortcuts import render, redirect
from rest_framework import viewsets
from .models import Order, OrderItem, Return
from .serializers import OrderSerializer, OrderItemSerializer, ReturnSerializer
from .forms import OrderForm, OrderItemForm


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer


class ReturnViewSet(viewsets.ModelViewSet):
    queryset = Return.objects.all()
    serializer_class = ReturnSerializer


def order_list(request):
    orders = Order.objects.select_related('customer').all()[:100]
    return render(request, 'orders/list.html', {'orders': orders})


def order_add(request):
    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        item_form = OrderItemForm(request.POST)
        if order_form.is_valid() and item_form.is_valid():
            order = order_form.save(commit=False)
            order.total_amount = 0
            order.save()

            item = item_form.save(commit=False)
            item.order = order
            item.save()

            order.total_amount = item.quantity * item.unit_price
            order.save()

            return redirect('order_list')
    else:
        order_form = OrderForm()
        item_form = OrderItemForm()
    return render(request, 'orders/form.html', {'order_form': order_form, 'item_form': item_form})


def return_list(request):
    returns = Return.objects.select_related('order', 'product').all()[:100]
    return render(request, 'orders/returns_list.html', {'returns': returns})