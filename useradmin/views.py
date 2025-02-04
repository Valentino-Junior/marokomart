from django.shortcuts import render, redirect
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.contrib.auth.hashers import check_password


from core.models import *
from userauths.models import Profile, User, ContactUs
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
from django.db.models import Sum, F
from django.core.paginator import Paginator


from django.utils import timezone
from django.db.models import Q 

from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from .utils.email_thread import send_email_threaded
from django.conf import settings

@admin_required
def dashboard(request):
    time_period = request.GET.get('time_period', 'total')
    
    # Get the current date and time
    current_date = timezone.now().date()
    
    # Initialize the date range based on the selected time period
    if time_period == 'day':
        start_date = current_date
        end_date = current_date + datetime.timedelta(days=1)
    elif time_period == 'week':
        start_date = current_date - datetime.timedelta(days=current_date.weekday())
        end_date = start_date + datetime.timedelta(days=7)
    elif time_period == 'month':
        start_date = current_date.replace(day=1)
        end_date = (start_date + datetime.timedelta(days=32)).replace(day=1)
    elif time_period == 'previous_month':
        end_date = current_date.replace(day=1)
        start_date = (end_date - datetime.timedelta(days=1)).replace(day=1)
    else:  # 'total' or any other value
        start_date = None
        end_date = None
    
    # Get all orders within the selected date range
    if start_date and end_date:
        all_orders = CartOrder.objects.filter(order_date__range=(start_date, end_date))
        all_paid_orders = all_orders.filter(paid_status=True)
    else:
        all_orders = CartOrder.objects.all()
        all_paid_orders = all_orders.filter(paid_status=True)
    
    # Initialize sales and profit variables
    total_sales = Decimal('0.00')
    total_profit = Decimal('0.00')
    paid_orders_count = 0
    total_orders = len(all_paid_orders)
    
    # Calculate sales and profits from paid orders
    for order in all_orders:
        if order.paid_status:
            paid_orders_count += 1
            
            # Calculate sales and profit for each order
            order_products = CartOrderProducts.objects.filter(order=order)
            order_sales = order_products.aggregate(total_sales=Sum('total'))['total_sales'] or Decimal('0.00')
            
            order_profit = Decimal('0.00')
            for order_product in order_products:
                try:
                    product = Product.objects.get(title=order_product.item)
                    order_profit += (order_product.price - product.buying_price) * order_product.qty
                except Product.DoesNotExist:
                    continue
            
            total_sales += order_sales
            total_profit += order_profit
    
    # Get products count based on items sold within the selected date range
    if start_date and end_date:
        products_count = CartOrderProducts.objects.filter(
            order__order_date__range=(start_date, end_date),
            order__paid_status=True
        ).values('item').distinct().count()
    else:
        products_count = CartOrderProducts.objects.filter(
            order__paid_status=True
        ).values('item').distinct().count()

    # Get top-selling products within the selected date range
    if start_date and end_date:
        top_selling_products = CartOrderProducts.objects.filter(
            order__order_date__range=(start_date, end_date),
            order__paid_status=True
        ).values('item').annotate(total_sold=Sum('qty')).order_by('-total_sold')[:5]
    else:
        top_selling_products = CartOrderProducts.objects.filter(
            order__paid_status=True
        ).values('item').annotate(total_sold=Sum('qty')).order_by('-total_sold')[:5]

    # Get the product titles for the top-selling products
    top_selling_products = [
        {
            'title': Product.objects.filter(title=product['item']).first().title,
            'total_sold': product['total_sold']
        }
        for product in top_selling_products
    ]


    
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
    
    context = {
        'total_sales': total_sales,
        'total_profit': total_profit,
        'products_count': products_count,
        'top_selling_products': top_selling_products,
        'orders_summary': {
            'total_count': total_orders,
            'paid_count': paid_orders_count,
            'pending_count': total_orders - paid_orders_count,
        },
        'stock_alerts': {
            'low_stock_count': len(low_stock_products),
            'products': low_stock_products,
        },
        'all_categories': all_categories,
        'new_customers': new_customers,
        'latest_orders': latest_orders,
        'time_period': time_period,
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
    products = Product.objects.all().select_related('category')
    categories = Category.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(
            Q(title__icontains=search_query) |
            Q(sku__icontains=search_query)
        )

    # Category filter
    category = request.GET.get('category', '')
    if category and category != 'all':
        products = products.filter(category__cid=category)

    context = {
        "all_products": products,
        "all_categories": categories,
        "selected_category": category,
    }
    return render(request, "useradmin/products.html", context)



@admin_required
def add_product(request):
    if request.method == "POST":
        form = AddProductForm(request.POST, request.FILES)
        if form.is_valid():
            # Create product but don't save to DB yet
            new_product = form.save(commit=False)
            new_product.user = request.user
            
            # Handle product type and status
            product_type = request.POST.get('product_type')
            
            # Set status flags based on product type
            if product_type == 'special_offer':
                new_product.is_special_offer = True
                new_product.special_offer_price = form.cleaned_data.get('special_offer_price')
                new_product.special_offer_ends = form.cleaned_data.get('special_offer_ends')
                new_product.is_new_arrival = False
            elif product_type == 'new_arrival':
                new_product.is_new_arrival = True
                new_product.new_arrival_ends = form.cleaned_data.get('new_arrival_ends')
                new_product.is_special_offer = False
            else:
                new_product.is_special_offer = False
                new_product.is_new_arrival = False

            # Save the product
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
            
            # Handle product type and status
            product_type = request.POST.get('product_type')
            
            # Reset all status fields first
            new_form.is_special_offer = False
            new_form.is_new_arrival = False
            
            # Set fields based on product type
            if product_type == 'special_offer':
                new_form.is_special_offer = True
                new_form.special_offer_price = form.cleaned_data.get('special_offer_price')
                new_form.special_offer_ends = form.cleaned_data.get('special_offer_ends')
            elif product_type == 'new_arrival':
                new_form.is_new_arrival = True
                new_form.new_arrival_ends = form.cleaned_data.get('new_arrival_ends')
                
            
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
    # Get all orders with related data
    orders = CartOrder.objects.select_related('shipping_address').order_by('-order_date')
    
    # Mark all unviewed orders as viewed
    CartOrder.objects.filter(is_viewed=False).update(is_viewed=True)

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        orders = orders.filter(
            Q(oid__icontains=search_query) |
            Q(shipping_address__full_name__icontains=search_query) |
            Q(shipping_address__email__icontains=search_query)
        )

    # Status filter
    status = request.GET.get('status')
    if status and status != 'all':
        orders = orders.filter(product_status=status)

    # Pagination
    items_per_page = int(request.GET.get('show', 20))
    paginator = Paginator(orders, items_per_page)
    page = request.GET.get('page')
    orders = paginator.get_page(page)

    context = {
        'orders': orders,
        'search_query': search_query,
        'current_status': status,
        'items_per_page': items_per_page,
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
def get_orders_count(request):
    count = CartOrder.get_unread_count()
    return JsonResponse({'count': count})


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

# views.py
@admin_required
def shop_page(request):
   # Get products and basic stats
   products = Product.objects.filter(user=request.user)
   total_orders = CartOrder.objects.filter(paid_status=True)
   total_order_items = CartOrderProducts.objects.filter(order__paid_status=True)

   # Calculate revenue
   revenue = total_orders.aggregate(total=Sum('price'))['total'] or 0
   
   # Calculate total sales quantity
   total_sales = total_order_items.aggregate(qty=Sum('qty'))['qty'] or 0
   
   # Calculate total cost and profit
   total_cost = 0
   total_profit = 0
   
   for item in total_order_items:
       try:
           product = Product.objects.get(title=item.item)
           item_cost = product.buying_price * item.qty
           item_profit = (item.price - product.buying_price) * item.qty
           total_cost += item_cost
           total_profit += item_profit
       except Product.DoesNotExist:
           continue

   context = {
       'products': products,
       'revenue': revenue,
       'total_sales': total_sales,
       'total_profit': total_profit,
       'total_cost': total_cost,
       'profit_margin': (total_profit/revenue * 100) if revenue > 0 else 0
   }
   return render(request, "useradmin/shop_page.html", context)


@admin_required
def product_reviews(request):
    reviews = ProductReview.objects.select_related('user', 'product').order_by('-date')
    # Mark all as viewed
    ProductReview.objects.filter(is_viewed=False).update(is_viewed=True)
    return render(request, "useradmin/product_reviews.html", {'reviews': reviews})

@admin_required
def get_product_review_count(request):
    count = ProductReview.get_unread_count()
    return JsonResponse({'count': count})


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
        profile.country = country

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


@admin_required
def category_list(request):
    categories = Category.objects.all()
    return render(request, 'useradmin/category_management.html', {'categories': categories})


@admin_required
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
    
@admin_required
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


@admin_required
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


@admin_required
def coupon_list(request):
    coupons = Coupon.objects.all().order_by('-created_at')
    return render(request, 'useradmin/coupon_management.html', {'coupons': coupons})


@admin_required
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


@admin_required
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
    

@admin_required
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


@admin_required
def contact_messages(request):
    messages_list = ContactUs.objects.all().order_by('-created_at')
    # Mark all as viewed
    ContactUs.objects.filter(is_viewed=False).update(is_viewed=True)
    
    paginator = Paginator(messages_list, 10)  # Show 10 messages per page
    page = request.GET.get('page')
    messages = paginator.get_page(page)
    
    return render(request, 'useradmin/contact_messages.html', {'messagez': messages})



@admin_required
def get_contact_message_count(request):
    count = ContactUs.get_unread_count()
    return JsonResponse({'count': count})


@admin_required
def get_unread_tickets_count(request):
    count = SupportTicket.get_unread_count()
    return JsonResponse({'count': count})


@admin_required
def support_tickets(request):
    # Mark all unread tickets as viewed
    SupportTicket.objects.filter(is_viewed=False).update(is_viewed=True)
    tickets = SupportTicket.objects.all().order_by('-created_at')
    return render(request, 'useradmin/support_ticket.html', {'tickets': tickets})



@admin_required
def get_ticket_details(request, ticket_id):
    try:
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        
        ticket_data = {
            'id': ticket.id,
            'order_id': ticket.order.oid,
            'username': ticket.user.username,
            'issue_type': ticket.get_issue_type_display(),
            'status': ticket.status,
            'message': ticket.message,
            'admin_response': ticket.admin_response,
            'created_at': ticket.created_at.strftime('%B %d, %Y %I:%M %p')
        }
        
        return JsonResponse({
            'success': True,
            'ticket': ticket_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@admin_required
def respond_to_ticket(request, ticket_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        ticket = get_object_or_404(SupportTicket, id=ticket_id)
        
        # Update ticket
        status = request.POST.get('status')
        admin_response = request.POST.get('admin_response')
        
        if not all([status, admin_response]):
            return JsonResponse({
                'success': False,
                'message': 'Both status and response are required'
            })
        
        ticket.status = status
        ticket.admin_response = admin_response
        ticket.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })
    

@admin_required
def order_reviews(request):
    reviews = Order_Review.objects.select_related('user', 'order').order_by('-created_at')
    unread_reviews = Order_Review.objects.filter(is_viewed=False).count()
    context = {
        'reviews': reviews,
        'unread_reviews': unread_reviews
    }
    # Mark all as viewed
    Order_Review.objects.filter(is_viewed=False).update(is_viewed=True)
    return render(request, 'useradmin/order_reviews.html', context)


@admin_required
def get_order_review_details(request, review_id):
    try:
        review = get_object_or_404(Order_Review, id=review_id)
        review_data = {
            'id': review.id,
            'order_id': review.order.oid,
            'username': review.user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%B %d, %Y %I:%M %p')
        }
        return JsonResponse({
            'success': True,
            'review': review_data
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })

@admin_required
def get_unread_order_reviews_count(request):
    count = Order_Review.objects.filter(is_viewed=False).count()
    return JsonResponse({'count': count})



@admin_required
@require_http_methods(["POST"])
def share_coupon(request, pk):
    try:
        coupon = get_object_or_404(Coupon, pk=pk)
        data = json.loads(request.body)
        
        subject = data.get('subject')
        message = data.get('message')
        share_with_all = data.get('share_with_all', False)
        selected_users = data.get('selected_users', [])


        if not subject or not message:
            return JsonResponse({
                'success': False,
                'message': 'Subject and message are required'
            }, status=400)

        # Get target users
        if share_with_all:
            users = User.objects.filter(is_active=True)
        else:
            if not selected_users:
                return JsonResponse({
                    'success': False,
                    'message': 'No recipients selected'
                }, status=400)
            users = User.objects.filter(id__in=selected_users, is_active=True)

        # Send emails
        for user in users:
            html_message = render_to_string('useradmin/emails/coupon_share.html', {
                
                'user': user,
                'coupon': coupon,
                'message': message,
                
            })
            
            send_email_threaded(
                subject=subject,
                html_message=html_message,
                recipient_list=[user.email]
            )
            
            # Update coupon shared_with field
            coupon.shared_with.add(user)

        return JsonResponse({
            'success': True,
            'message': f'Coupon shared with {users.count()} users'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@admin_required
def get_users_list(request):
    search = request.GET.get('search', '')
    users = User.objects.filter(is_active=True)
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search)
        )
    
    users_data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email
    } for user in users[:100]]  # Limit to 100 users for performance
    
    return JsonResponse({'users': users_data})


@admin_required
def client_list(request):
    clients = User.objects.filter(is_staff=False, is_superuser=False).select_related('profile')
    return render(request, 'useradmin/clients.html', {'clients': clients})

@admin_required
def update_client(request, pk):
    if request.method == 'POST':
        try:
            client = User.objects.get(pk=pk)
            profile = client.profile
            
            client.email = request.POST.get('email')
            client.is_active = request.POST.get('is_active') == 'on'
            client.save()
            
            profile.full_name = request.POST.get('full_name')
            profile.phone = request.POST.get('phone')
            profile.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@admin_required
def delete_client(request, pk):
    if request.method == 'POST':
        try:
            client = User.objects.get(pk=pk)
            client.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})