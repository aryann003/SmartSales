from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from .models import Customer
from .serializers import CustomerSerializer

from core.permissions import IsSalesperson




class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsSalesperson]


def customer_list(request):
    customers = Customer.objects.all()[:100]
    return render(request, 'customers/list.html', {'customers' :customers})



from django.shortcuts import render, redirect
from .forms import CustomerForm

def customer_add(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/form.html', {'form': form})