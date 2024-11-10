from django.shortcuts import render, redirect
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.hashers import check_password


from core.models import CartOrder, CartOrderProducts, Product, Category, ProductReview, ProductImages
from userauths.models import Profile, User
from useradmin.forms import AddProductForm, EditProductForm, CategoryForm
from useradmin.decorators import admin_required
from django.http import JsonResponse

import datetime
import os
from django.shortcuts import render, get_object_or_404


@admin_required
def dashboard(request):
    revenue = CartOrder.objects.aggregate(price=Sum("price"))
    total_orders_count = CartOrder.objects.all()
    all_products = Product.objects.all()
    all_categories = Category.objects.all()
    new_customers = User.objects.all().order_by("-id")[:6]
    latest_orders = CartOrder.objects.all()

    this_month = datetime.datetime.now().month
    monthly_revenue = CartOrder.objects.filter(order_date__month=this_month).aggregate(price=Sum("price"))

    
    context = {
        "monthly_revenue": monthly_revenue,
        "revenue": revenue,
        "all_products": all_products,
        "all_categories": all_categories,
        "new_customers": new_customers,
        "latest_orders": latest_orders,
        "total_orders_count": total_orders_count,
    }
    return render(request, "useradmin/dashboard.html", context)

@admin_required
def products(request):
    all_products = Product.objects.all()
    all_categories = Category.objects.all()
    
    context = {
        "all_products": all_products,
        "all_categories": all_categories,
    }
    return render(request, "useradmin/products.html", context)


@admin_required
def add_product(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the main product first
            new_product = form.save(commit=False)
            new_product.user = request.user
            new_product.save()
            form.save_m2m()

            # Handle multiple images
            files = request.FILES.getlist('additional_images')
            for f in files:
                ProductImages.objects.create(
                    product=new_product,
                    images=f
                )

            return redirect("useradmin:dashboard-products")
        else:
            print(form.errors)  # For debugging
    else:
        form = AddProductForm()
    
    context = {
        'form': form
    }
    return render(request, "useradmin/add-products.html", context)




@admin_required
def edit_product(request, pid):
    product = Product.objects.get(pid=pid)
    product_images = ProductImages.objects.filter(product=product)

    if request.method == "POST":
        form = EditProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            new_form = form.save(commit=False)
            
            # Handle main image
            if request.FILES.get('image'):
                new_form.image = request.FILES['image']
            
            new_form.save()
            form.save_m2m()

            # Handle additional images
            if request.FILES.getlist('additional_images'):
                for img in request.FILES.getlist('additional_images'):
                    ProductImages.objects.create(
                        product=product,
                        images=img
                    )

            return redirect("useradmin:dashboard-products")
    else:
        form = EditProductForm(instance=product)
    
    context = {
        'form': form,
        'product': product,
        'product_images': product_images,
    }
    return render(request, "useradmin/edit-products.html", context)


@admin_required
def delete_product_image(request, pid, image_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            image = ProductImages.objects.get(id=image_id, product__pid=pid)
            if image.images:
                if os.path.exists(image.images.path):
                    os.remove(image.images.path)
            image.delete()
            return JsonResponse({'status': 'success'})
        except ProductImages.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Image not found'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@admin_required
def delete_product(request, pid):
    product = Product.objects.get(pid=pid)
    product.delete()
    return redirect("useradmin:dashboard-products")

@admin_required
def orders(request):
    orders = CartOrder.objects.all()
    context = {
        'orders':orders,
    }
    return render(request, "useradmin/orders.html", context)

@admin_required
def order_detail(request, id):
    order = CartOrder.objects.get(id=id)
    order_items = CartOrderProducts.objects.filter(order=order)
    context = {
        'order':order,
        'order_items':order_items
    }
    return render(request, "useradmin/order_detail.html", context)

@admin_required
@csrf_exempt
def change_order_status(request, oid):
    order = CartOrder.objects.get(oid=oid)
    if request.method == "POST":
        status = request.POST.get("status")
        print("status =======", status)
        messages.success(request, f"Order status changed to {status}")
        order.product_status = status
        order.save()
    
    return redirect("useradmin:order_detail", order.id)

@admin_required
def shop_page(request):
    products = Product.objects.filter(user=request.user)
    revenue = CartOrder.objects.filter(paid_status=True).aggregate(price=Sum("price"))
    total_sales = CartOrderProducts.objects.filter(order__paid_status=True).aggregate(qty=Sum("qty"))

    context = {
        'products':products,
        'revenue':revenue,
        'total_sales':total_sales,
    }
    return render(request, "useradmin/shop_page.html", context)

@admin_required
def reviews(request):
    reviews = ProductReview.objects.all()
    context = {
        'reviews':reviews,
    }
    return render(request, "useradmin/reviews.html", context)

@admin_required
def settings(request):
    profile = Profile.objects.get(user=request.user)

    if request.method == "POST":
        image = request.FILES.get("image")
        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        bio = request.POST.get("bio")
        address = request.POST.get("address")
        country = request.POST.get("country")
        print("image ===========", image)
        
        if image != None:
            profile.image = image
        profile.full_name = full_name
        profile.phone = phone
        profile.bio = bio
        profile.address = address
        profile.county = country

        profile.save()
        messages.success(request, "Profile Updated Successfully")
        return redirect("useradmin:settings")
    
    context = {
        'profile':profile,
    }
    return render(request, "useradmin/settings.html", context)

@admin_required
def change_password(request):
    user = request.user

    if request.method == "POST":
        old_password = request.POST.get("old_password")
        new_password = request.POST.get("new_password")
        confirm_new_password = request.POST.get("confirm_new_password")

        if confirm_new_password != new_password:
            messages.error(request, "Confirm Password and New Password Does Not Match")
            return redirect("useradmin:change_password")
        
        if check_password(old_password, user.password):
            user.set_password(new_password)
            user.save()
            messages.success(request, "Password Changed Successfully")
            return redirect("useradmin:change_password")
        else:
            messages.error(request, "Old password is not correct")
            return redirect("useradmin:change_password")
    
    return render(request, "useradmin/change_password.html")



def category_list(request):
    categories = Category.objects.all()
    return render(request, 'useradmin/category_management.html', {'categories': categories})

def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Category created successfully'
            })
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })

def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            # Delete old image if new one is uploaded
            if request.FILES.get('image') and category.image:
                if os.path.isfile(category.image.path):
                    os.remove(category.image.path)
            form.save()
            return JsonResponse({
                'success': True,
                'message': 'Category updated successfully'
            })
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })

def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        if category.image:
            if os.path.isfile(category.image.path):
                os.remove(category.image.path)
        category.delete()
        return JsonResponse({
            'success': True,
            'message': 'Category deleted successfully'
        })
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })
