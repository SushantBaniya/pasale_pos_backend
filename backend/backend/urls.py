"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django import views
from django.contrib import admin
from django.urls import path, include
from orderCart.views import OrderCartView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    
    # Order Cart URLs
    path('api/cart/', OrderCartView.as_view(), name='cart_items_all'),
    path('api/cart/business/<int:business_id>/', OrderCartView.as_view(), name='cart_items'),
    path('api/cart/business/<int:business_id>/customer/<int:customer_id>/', OrderCartView.as_view(), name='cart_items_by_customer'),
]  
