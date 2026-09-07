from django.db import models

# Create your models here.
from customers.models import Customer
from products.models import Product



class Order(models.Model):
    STATUS_CHOICES =[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled')
    ]
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='orders')
    order_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"Order {self.id} - {self.customer.name}"

    
        


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} for Order {self.order.id}"




class Return(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='returns')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='returns')
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=255, blank=True)
    return_date = models.DateField()

    def __str__(self):
        return f"Return - {self.product.name} ({self.quantity})"