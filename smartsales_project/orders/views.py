from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Order, OrderItem, Return
from .serializers import OrderSerializer, OrderItemSerializer, ReturnSerializer



class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer



class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer



class ReturnViewSet(viewsets.ModelViewSet):
    queryset = Return.objects.all()
    serializer_class = ReturnSerializer