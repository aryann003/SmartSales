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



