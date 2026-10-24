from django.shortcuts import render
from rest_framework import viewsets
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from django.contrib.auth.decorators import login_required

from core.permissions import CanManageCatalog





class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.order_by('id')
    serializer_class = CategorySerializer
    permission_classes = [CanManageCatalog]



class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').order_by('id')
    serializer_class = ProductSerializer
    permission_classes = [CanManageCatalog]
# Create your views here.



from django.shortcuts import render, redirect
from .forms import ProductForm


@login_required
def product_list(request):
    products = Product.objects.select_related('category').all()[:100]
    return render(request, 'products/list.html', {'products': products})


@login_required
def product_add(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'products/form.html', {'form': form})