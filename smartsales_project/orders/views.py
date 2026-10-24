from django.shortcuts import render, redirect
from rest_framework import viewsets
from .models import Order, OrderItem, Return
from .serializers import OrderSerializer, OrderItemSerializer, ReturnSerializer
from .forms import OrderForm, OrderItemForm
from django.contrib.auth.decorators import login_required
from django.db import transaction

from core.permissions import CanManageSalesData



class OrderViewSet(viewsets.ModelViewSet):
    # Items are nested in the serializer, so prefetch them: one extra query per
    # page instead of one per order.
    queryset = Order.objects.prefetch_related('items').order_by('-order_date', '-id')
    serializer_class = OrderSerializer
    permission_classes = [CanManageSalesData]


class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.order_by('id')
    serializer_class = OrderItemSerializer
    permission_classes = [CanManageSalesData]


class ReturnViewSet(viewsets.ModelViewSet):
    queryset = Return.objects.order_by('-return_date', '-id')
    serializer_class = ReturnSerializer
    permission_classes = [CanManageSalesData]

@login_required
def order_list(request):
    orders = Order.objects.select_related('customer').order_by('-order_date', '-id')[:100]
    return render(request, 'orders/list.html', {'orders': orders})

@login_required
def order_add(request):
    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        item_form = OrderItemForm(request.POST)
        if order_form.is_valid() and item_form.is_valid():
            quantity = item_form.cleaned_data['quantity']
            unit_price = item_form.cleaned_data['unit_price']

            # Order and item are saved together or not at all, and the
            # webhook only fires once both are committed.
            with transaction.atomic():
                order = order_form.save(commit=False)
                order.total_amount = quantity * unit_price
                order.save()

                item = item_form.save(commit=False)
                item.order = order
                item.save()

            return redirect('order_list')
    else:
        order_form = OrderForm()
        item_form = OrderItemForm()
    return render(request, 'orders/form.html', {'order_form': order_form, 'item_form': item_form})

@login_required
def return_list(request):
    returns = Return.objects.select_related('order', 'product').all()[:100]
    return render(request, 'orders/returns_list.html', {'returns': returns})