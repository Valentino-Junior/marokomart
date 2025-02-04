from ast import Add
from core.models import *
from django.db.models import Min, Max
from django.contrib import messages

def default(request):
    categories = Category.objects.all()

    min_max_price = Product.objects.aggregate(Min("price"), Max("price"))

    if request.user.is_authenticated:
        try:
            wishlist = wishlist_model.objects.filter(user=request.user)
        except:
            messages.warning(request, "You need to login before accessing your wishlist.")
            wishlist = 0
    else:
        wishlist = 0

    
    return {
        'categories':categories,
        'wishlist':wishlist,
        'min_max_price':min_max_price,
    }