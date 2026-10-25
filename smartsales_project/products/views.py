from django.shortcuts import render
from django.core.paginator import Paginator
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
    products = Product.objects.select_related('category').order_by('id')
    per_page = request.GET.get('per_page', '25')
    if per_page not in {'10', '25', '50', '100'}:
        per_page = '25'
    page_obj = Paginator(products, int(per_page)).get_page(request.GET.get('page'))
    return render(request, 'products/list.html', {
        'products': page_obj,
        'page_obj': page_obj,
        'per_page': per_page,
    })


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