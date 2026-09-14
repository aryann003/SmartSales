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




from django.shortcuts import render, redirect
from .forms import OrderForm

def order_list(request):
    orders = Order.objects.select_related('customer').all()[:100]
    return render(request, 'orders/list.html', {'orders': orders})

def order_add(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('order_list')
    else:
        form = OrderForm()
    return render(request, 'orders/form.html', {'form': form})



from .models import Return

def return_list(request):
    returns = Return.objects.all()
    return render(request, 'orders/returns_list.html', {'returns': returns})