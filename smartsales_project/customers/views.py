from django.shortcuts import render
from django.core.paginator import Paginator

# Create your views here.
from rest_framework import viewsets
from .models import Customer
from .serializers import CustomerSerializer

from core.permissions import CanManageSalesData
from django.contrib.auth.decorators import login_required



class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.order_by('id')
    serializer_class = CustomerSerializer
    permission_classes = [CanManageSalesData]

@login_required
def customer_list(request):
    customers = Customer.objects.order_by('id')
    per_page = request.GET.get('per_page', '25')
    if per_page not in {'10', '25', '50', '100'}:
        per_page = '25'
    page_obj = Paginator(customers, int(per_page)).get_page(request.GET.get('page'))
    return render(request, 'customers/list.html', {
        'customers': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
    })



from django.shortcuts import render, redirect
from .forms import CustomerForm


@login_required
def customer_add(request):
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')
    else:
        form = CustomerForm()
    return render(request, 'customers/form.html', {'form': form})