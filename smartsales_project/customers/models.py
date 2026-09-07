from django.db import models

# Create your models here.


class Customer(models.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    country = models.CharField(max_length=100)
    signup_date = models.DateField()


    def __str__(self):
        return self.name

