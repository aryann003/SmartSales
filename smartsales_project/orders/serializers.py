from rest_framework import serializers
from .models import Order, OrderItem, Return

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = '__all__'
        extra_kwargs = {
            'quantity': {'min_value': 1},
            'unit_price': {'min_value': 0},
        }

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'
        extra_kwargs = {'total_amount': {'min_value': 0}}

class ReturnSerializer(serializers.ModelSerializer):
    class Meta:
        model = Return
        fields = '__all__'
        extra_kwargs = {'quantity': {'min_value': 1}}