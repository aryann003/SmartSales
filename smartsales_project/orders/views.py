from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from rest_framework import viewsets
from .models import Order, OrderItem, Return
from .serializers import OrderSerializer, OrderItemSerializer, ReturnSerializer
from .forms import OrderForm, OrderItemForm, ReturnForm
from django.contrib.auth.decorators import login_required
from django.db import transaction

from core.permissions import CanManageSalesData, get_role



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
    orders = Order.objects.select_related('customer').order_by('-order_date', '-id')
    per_page = request.GET.get('per_page', '25')
    if per_page not in {'10', '25', '50', '100'}:
        per_page = '25'
    page_obj = Paginator(orders, int(per_page)).get_page(request.GET.get('page'))
    return render(request, 'orders/list.html', {
        'orders': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
    })

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
    returns = Return.objects.select_related('order__customer', 'product').order_by('-return_date', '-id')
    per_page = request.GET.get('per_page', '25')
    if per_page not in {'10', '25', '50', '100'}:
        per_page = '25'
    page_obj = Paginator(returns, int(per_page)).get_page(request.GET.get('page'))
    return render(request, 'orders/returns_list.html', {
        'returns': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
    })


@login_required
def return_add(request):
    if get_role(request.user) not in {'admin', 'manager', 'salesperson'}:
        return HttpResponseForbidden()
    if request.method == 'POST':
        form = ReturnForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('return_list')
    else:
        form = ReturnForm()
    return render(request, 'orders/return_form.html', {'form': form})