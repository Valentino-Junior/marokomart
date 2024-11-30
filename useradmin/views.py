from django.shortcuts import render, redirect
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.hashers import check_password


from core.models import CartOrder, CartOrderProducts, Product, Category, ProductReview, ProductImages
from userauths.models import Profile, User
from useradmin.forms import AddProductForm, EditProductForm, CategoryForm, CouponForm, Coupon
from useradmin.decorators import admin_required
from django.http import JsonResponse

import datetime
import os
from django.shortcuts import render, get_object_or_404

from decimal import Decimal
from collections import defaultdict
import json
from core.views import update_product_stock 



@admin_required
def dashboard(request):
    # Get all orders
    all_orders = CartOrder.objects.all()
    
    # Initialize revenue and order counts
    total_revenue = Decimal('0.00')
    monthly_revenue = Decimal('0.00')
    paid_orders_count = 0
    total_orders = len(all_orders)
    
    # Get current month
    current_month = datetime.datetime.now().month
    
    # Calculate revenues from paid orders
    for order in all_orders:
        if order.paid_status:
            paid_orders_count += 1
            total_revenue += order.price
            
            # Add to monthly revenue if order is from current month
            if order.order_date.month == current_month:
                monthly_revenue += order.price
    
    # Get products data and check for low stock
    all_products = Product.objects.all()
    low_stock_products = []
    for product in all_products:
        try:
            current_stock = int(product.stock_count)
            if current_stock <= product.low_stock_threshold:
                low_stock_products.append({
                    'product': product,
                    'current_stock': current_stock,
                    'threshold': product.low_stock_threshold,
                    'status': 'Out of Stock' if current_stock == 0 else 'Low Stock'
                })
        except (ValueError, TypeError):
            continue

    # Get other data
    all_categories = Category.objects.all()
    new_customers = User.objects.all().order_by("-id")[:6]
    latest_orders = all_orders.select_related('shipping_address').order_by('-order_date')[:10]
    
    # Calculate payment rate
    payment_rate = (paid_orders_count / total_orders * 100) if total_orders > 0 else 0
    
    context = {
        "revenue": {
            "price": "{:,.2f}".format(total_revenue)
        },
        "monthly_revenue": {
            "price": "{:,.2f}".format(monthly_revenue)
        },
        "orders_summary": {
            "total_count": total_orders,
            "paid_count": paid_orders_count,
            "pending_count": total_orders - paid_orders_count,
            "payment_rate": round(payment_rate, 1)
        },
        "stock_alerts": {
            "low_stock_count": len(low_stock_products),
            "products": low_stock_products,
        },
        "inventory": {
            "total_products": all_products.count(),
            "total_categories": all_categories.count(),
        },
        "all_products": all_products,
        "all_categories": all_categories,
        "new_customers": new_customers,
        "latest_orders": latest_orders,
    }
    return render(request, "useradmin/dashboard.html", context)


@admin_required
def update_payment_status(request, oid):
    if request.method == 'POST':
        try:
            order = get_object_or_404(CartOrder, oid=oid)
            
            # Get current and new payment status
            current_status = order.paid_status
            new_status = 'paid_status' in request.POST
            
            # If it's a cash payment being marked as paid
            if order.payment_method == 'cash' and not current_status and new_status:
                # Get order items and update stock
                order_items = CartOrderProducts.objects.filter(order=order)
                
                for item in order_items:
                    try:
                        # Get product directly from database
                        product = Product.objects.get(title=item.item)
                        
                        # Convert current stock to int and subtract quantity
                        current_stock = int(product.stock_count) if product.stock_count else 0
                        new_stock = max(0, current_stock - item.qty)
                        
                        # Update product stock
                        product.stock_count = str(new_stock)
                        product.save()
                        
                    except Product.DoesNotExist:
                        continue
                    except Exception as e:
                        print(f"Error updating stock for {item.item}: {str(e)}")
                        continue
                
                messages.success(request, 'Payment marked as paid and stock updated')
            
            # Update payment status
            order.paid_status = new_status
            order.save()
            
            if not (order.payment_method == 'cash' and not current_status and new_status):
                messages.success(request, f'Payment status updated to {"Paid" if new_status else "Unpaid"}')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    return redirect(request.META.get('HTTP_REFERER', 'useradmin:orders'))


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
    orders = CartOrder.objects.select_related('shipping_address').all()
    context = {
        'orders':orders,
    }
    return render(request, "useradmin/orders.html", context)

@admin_required
def order_detail(request, id):
    order = CartOrder.objects.select_related('shipping_address').get(id=id)
    order_items = CartOrderProducts.objects.filter(order=order)
    context = {
        'order': order,
        'order_items': order_items
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



def coupon_list(request):
    coupons = Coupon.objects.all().order_by('-created_at')
    return render(request, 'useradmin/coupon_management.html', {'coupons': coupons})

def coupon_create(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Coupon created successfully',
                'coupon': {
                    'id': coupon.id,
                    'code': coupon.code,
                    'discount': coupon.discount,
                    'active': coupon.active,
                    'expiry_date': coupon.expiry_date.strftime('%Y-%m-%d %H:%M') if coupon.expiry_date else None,
                    'usage_limit': coupon.usage_limit,
                    'times_used': coupon.times_used
                }
            })
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })

def coupon_update(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            coupon = form.save()
            return JsonResponse({
                'success': True,
                'message': 'Coupon updated successfully'
            })
        return JsonResponse({
            'success': False,
            'errors': form.errors
        })

def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        coupon.delete()
        return JsonResponse({
            'success': True,
            'message': 'Coupon deleted successfully'
        })
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })