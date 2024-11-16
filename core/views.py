from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from requests import session
import stripe
from taggit.models import Tag
from core.models import Coupon, Product, Category, CartOrder, CartOrderProducts, ProductImages, ProductReview, wishlist_model, Address, ShippingAddress
from userauths.models import ContactUs, Profile
from core.forms import ProductReviewForm
from userauths.forms import ProfileForm


from django.template.loader import render_to_string
from django.contrib import messages

from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from paypal.standard.forms import PayPalPaymentsForm
from django.contrib.auth.decorators import login_required

import calendar
from django.db.models import Count, Avg, FloatField, OuterRef, Subquery
from django.db.models.functions import ExtractMonth
from django.core import serializers

from django.db.models.functions import Coalesce
import math

from django.db.models import Q
from django.core.paginator import Paginator


from django.shortcuts import render
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.contrib import messages

from decimal import Decimal
from django.views.decorators.http import require_http_methods



def index(request):
    products = Product.objects.filter(product_status="published")
    sort_by = request.GET.get('sort_by', '')
    
    # Apply sorting
    if sort_by == 'price_low_high':
        products = products.order_by('price', '-id')
    elif sort_by == 'price_high_low':
        products = products.order_by('-price', '-id')
    else:
        products = products.order_by("-id")
    
    context = {
        "products": products,
        "current_sort": sort_by,
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # If AJAX request, return only the product grid
        best_deal_html = render_to_string(
            'core/includes/best_deal.html',
            context,
            request=request
        )
        return JsonResponse({
            'product_grid': best_deal_html,
            'product_count': products.count(),
        })

    return render(request, 'core/index.html', context)



def product_list_view(request):
    """Main view for product list page"""
    products = Product.objects.filter(product_status="published")
    sort_by = request.GET.get('sort_by', '')
    
    # Apply sorting
    if sort_by == 'price_low_high':
        products = products.order_by('price', '-id')
    elif sort_by == 'price_high_low':
        products = products.order_by('-price', '-id')
    else:
        products = products.order_by("-id")
    
    context = {
        "products": products,
        "current_sort": sort_by,
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # If AJAX request, return only the product grid
        product_grid_html = render_to_string(
            'core/includes/product_grid.html',
            context,
            request=request
        )
        return JsonResponse({
            'product_grid': product_grid_html,
            'product_count': products.count(),
        })
    
    return render(request, 'core/product-list.html', context)



def category_list_view(request):
    """
    View for category listing with sorting options
    """
    # Get base queryset
    categories = Category.objects.all()
    
    # Add annotations for product and review counts
    categories = categories.annotate(
        total_products=Count('category', distinct=True),
        total_reviews=Count('category__reviews', distinct=True)
    )
    
    # Get sort parameter
    sort_by = request.GET.get('sort_by', '')
    
    # Apply sorting
    if sort_by == 'most_products':
        categories = categories.order_by('-total_products', 'title')
    elif sort_by == 'most_reviews':
        categories = categories.order_by('-total_reviews', 'title')
    elif sort_by == 'recently_added':
        # Assuming you want to sort by the most recent product in each category
        categories = categories.annotate(
            latest_product=Subquery(
                Product.objects.filter(
                    category=OuterRef('pk')
                ).order_by('-date').values('date')[:1]
            )
        ).order_by('-latest_product', 'title')
    else:
        categories = categories.order_by('title')

    context = {
        "categories": categories,
        "current_sort": sort_by
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        grid_html = render_to_string(
            'core/includes/category_grid.html',
            context,
            request=request
        )
        return JsonResponse({
            'html': grid_html,
            'count': categories.count()
        })
    
    return render(request, "core/category-list.html", context)



def category_product_list__view(request, cid):

    category = Category.objects.get(cid=cid) 
    products = Product.objects.filter(product_status="published", category=category)

    context = {
        "category":category,
        "products":products,
    }
    return render(request, "core/category-product-list.html", context)



def product_detail_view(request, pid):
    # Get product or return 404
    product = get_object_or_404(Product, pid=pid)

    # Get all product images including the main image
    product_images = ProductImages.objects.filter(product=product).order_by('date')
    
    # Get related products
    products = Product.objects.filter(category=product.category).exclude(pid=pid)
    
    # Get all reviews for the product
    reviews = ProductReview.objects.filter(product=product).order_by("-date")
    
    # Calculate average rating
    average_rating = reviews.aggregate(
        rating=Coalesce(Avg('rating', output_field=FloatField()), 0.0)
    )
    
    # Get rating distribution
    rating_distribution = reviews.values('rating').annotate(
        count=Count('rating')
    ).order_by('-rating')
    
    # Initialize counts dictionary
    rating_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    
    # Update with actual counts
    for item in rating_distribution:
        rating_counts[item['rating']] = item['count']
    
    # Find maximum count for scaling
    max_count = max(rating_counts.values()) if rating_counts.values() else 1
    
    # Prepare rating bars data
    rating_bars = []
    for rating in range(5, 0, -1):
        count = rating_counts[rating]
        
        # Calculate bar width
        if count == 0:
            width = 0
        elif count == max_count:
            width = 100
        else:
            log_count = math.log(count + 1)
            log_max = math.log(max_count + 1)
            width = min((log_count / log_max) * 100, 100)
            
        rating_bars.append({
            'rating': rating,
            'count': count,
            'width': width,
            'stars_filled': '★' * rating,
            'stars_empty': '☆' * (5 - rating)
        })
    
    # Handle review form and permissions
    make_review = True
    if request.user.is_authenticated:
        user_review_count = ProductReview.objects.filter(
            user=request.user, 
            product=product
        ).count()
        make_review = user_review_count == 0
    
    context = {
        "p": product,
        "product_images": product_images,
        "make_review": make_review,
        "review_form": ProductReviewForm(),
        "average_rating": average_rating,
        "reviews": reviews,
        "products": products,
        "total_reviews": reviews.count(),
        "rating_bars": rating_bars,
    }
    
    return render(request, "core/product-detail.html", context)





def ajax_add_review(request, pid):
    product = Product.objects.get(pk=pid)
    user = request.user 

    review = ProductReview.objects.create(
        user=user,
        product=product,
        review = request.POST['review'],
        rating = request.POST['rating'],
    )

    context = {
        'user': user.username,
        'review': request.POST['review'],
        'rating': request.POST['rating'],
    }

    average_reviews = ProductReview.objects.filter(product=product).aggregate(rating=Avg("rating"))

    return JsonResponse(
       {
         'bool': True,
        'context': context,
        'average_reviews': average_reviews
       }
    )


def search_view(request):
    query = request.GET.get("q")

    products = Product.objects.filter(title__icontains=query).order_by("-date")

    context = {
        "products": products,
        "query": query,
    }
    return render(request, "core/search.html", context)


def filter_product(request):
    categories = request.GET.getlist("category[]")
   

    min_price = request.GET['min_price']
    max_price = request.GET['max_price']

    products = Product.objects.filter(product_status="published").order_by("-id").distinct()

    products = products.filter(price__gte=min_price)
    products = products.filter(price__lte=max_price)


    if len(categories) > 0:
        products = products.filter(category__id__in=categories).distinct() 
    else:
        products = Product.objects.filter(product_status="published").order_by("-id").distinct()
       
    
    data = render_to_string("core/async/product-list.html", {"products": products})
    return JsonResponse({"data": data})


def add_to_cart(request):
    if request.method == 'GET':
        try:
            cart_product = {}
            product_id = request.GET['id']
            # Get quantity from request, default to 1 if not provided
            quantity = int(request.GET.get('quantity', '1'))
            
            cart_product[str(product_id)] = {
                'title': request.GET['title'],
                'qty': str(quantity),  # Use the quantity from request
                'price': request.GET['price'],
                'image': request.GET['image'],
                'pid': request.GET['pid'],
            }

            if 'cart_data_obj' in request.session:
                if str(product_id) in request.session['cart_data_obj']:
                    cart_data = request.session['cart_data_obj']
                    # Add the new quantity to existing quantity
                    cart_data[str(product_id)]['qty'] = str(
                        int(cart_data[str(product_id)]['qty']) + quantity
                    )
                    request.session['cart_data_obj'] = cart_data
                else:
                    cart_data = request.session['cart_data_obj']
                    cart_data.update(cart_product)
                    request.session['cart_data_obj'] = cart_data
            else:
                request.session['cart_data_obj'] = cart_product
            
            request.session.modified = True
            
            # Get the updated cart count by summing all quantities
            # Get the updated cart count
            cart_count = len(request.session['cart_data_obj'])
            
            return JsonResponse({
                "data": request.session['cart_data_obj'],
                'totalcartitems': cart_count,
                'status': 'success',
                'message': 'Item added to cart successfully!'
            })
            
        except Exception as e:
            print(f"Add to cart error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })


def update_cart(request):
    if request.method == 'GET':
        try:
            product_id = str(request.GET['id'])
            quantity = int(request.GET['qty'])
            
            cart_data = request.session.get('cart_data_obj', {})
            
            if product_id in cart_data:
                # Get and clean price
                price = float(str(cart_data[product_id]['price']).replace('Ksh', '').replace(',', '').strip())
                
                # Update quantity
                cart_data[product_id]['qty'] = str(quantity)
                
                # Calculate new subtotal
                subtotal = quantity * price
                cart_data[product_id]['subtotal'] = subtotal
                
                # Calculate new cart total
                cart_total = 0
                for item in cart_data.values():
                    try:
                        item_price = float(str(item['price']).replace('Ksh', '').replace(',', '').strip())
                        item_qty = int(item['qty'])
                        cart_total += item_price * item_qty
                    except (ValueError, TypeError):
                        continue
                
                # Update session
                request.session['cart_data_obj'] = cart_data
                request.session.modified = True
                
                return JsonResponse({
                    'status': 'success',
                    'subtotal': subtotal,
                    'cart_total': cart_total
                })
            
            return JsonResponse({
                'status': 'error',
                'message': 'Product not found in cart'
            })
            
        except (ValueError, TypeError) as e:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid quantity or price'
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })


def cart_view(request):
    try:
        cart_total_amount = 0
        cart_data = request.session.get('cart_data_obj', {})
        
        if cart_data:
            # Calculate subtotals and cart total
            for p_id, item in cart_data.items():
                try:
                    qty = int(str(item.get('qty', '1')).strip())
                    price = float(str(item.get('price', '0')).replace('Ksh', '').replace(',', '').strip())
                    
                    subtotal = qty * price
                    cart_total_amount += subtotal
                    
                    # Update item with subtotal
                    cart_data[p_id].update({
                        'qty': str(qty),
                        'price': str(price),
                        'subtotal': subtotal
                    })
                    
                except (ValueError, TypeError):
                    continue
            
            # Update session with calculated values
            request.session['cart_data_obj'] = cart_data
            request.session.modified = True
            
            return render(request, "core/cart.html", {
                "cart_data": cart_data,
                'totalcartitems': len(cart_data),
                'cart_total_amount': cart_total_amount
            })
        
        messages.warning(request, "Your cart is empty")
        return redirect("core:index")
        
    except Exception as e:
        print(f"Cart view error: {str(e)}")
        messages.error(request, "Error calculating cart total. Please try again.")
        return redirect("core:index")
    


def delete_item_from_cart(request):
    if request.method == 'GET':
        try:
            product_id = str(request.GET['id'])
            cart_data = request.session.get('cart_data_obj', {})
            
            if product_id in cart_data:
                # Remove item from cart
                del cart_data[product_id]
                request.session['cart_data_obj'] = cart_data
                request.session.modified = True
                
                # Calculate new cart total
                cart_total = 0
                for item in cart_data.values():
                    try:
                        price = float(str(item['price']).replace('Ksh', '').replace(',', '').strip())
                        qty = int(item['qty'])
                        cart_total += price * qty
                    except (ValueError, TypeError):
                        continue

                return JsonResponse({
                    'status': 'success',
                    'message': 'Item removed from cart',
                    'cart_total': cart_total,
                    'cart_count': len(cart_data)
                })
            
            return JsonResponse({
                'status': 'error',
                'message': 'Item not found in cart'
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })


def save_checkout_info(request):
    cart_total_amount = 0
    total_amount = 0
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        mobile = request.POST.get("mobile")
        address = request.POST.get("address")
        city = request.POST.get("city")
        state = request.POST.get("state")
        country = request.POST.get("country")

        print(full_name)
        print(email)
        print(mobile)
        print(address)
        print(city)
        print(state)
        print(country)

        request.session['full_name'] = full_name
        request.session['email'] = email
        request.session['mobile'] = mobile
        request.session['address'] = address
        request.session['city'] = city
        request.session['state'] = state
        request.session['country'] = country


        if 'cart_data_obj' in request.session:

            # Getting total amount for Paypal Amount
            for p_id, item in request.session['cart_data_obj'].items():
                total_amount += int(item['qty']) * float(item['price'])


            full_name = request.session['full_name']
            email = request.session['email']
            phone = request.session['mobile']
            address = request.session['address']
            city = request.session['city']
            state = request.session['state']
            country = request.session['country']

            # Create ORder Object
            order = CartOrder.objects.create(
                user=request.user,
                price=total_amount,
                # full_name=full_name,
                # email=email,
                # phone=phone,
                # address=address,
                # city=city,
                # state=state,
                # country=country,
            )

            del request.session['full_name']
            del request.session['email']
            del request.session['mobile']
            del request.session['address']
            del request.session['city']
            del request.session['state']
            del request.session['country']

            # Getting total amount for The Cart
            for p_id, item in request.session['cart_data_obj'].items():
                cart_total_amount += int(item['qty']) * float(item['price'])

                cart_order_products = CartOrderProducts.objects.create(
                    order=order,
                    invoice_no="INVOICE_NO-" + str(order.id), # INVOICE_NO-5,
                    item=item['title'],
                    image=item['image'],
                    qty=item['qty'],
                    price=item['price'],
                    total=float(item['qty']) * float(item['price'])
                )



        return redirect("core:checkout", order.oid)
    return redirect("core:checkout", order.oid)



@csrf_exempt
def create_checkout_session(request, oid):
    order = CartOrder.objects.get(oid=oid)
    stripe.api_key = settings.STRIPE_SECRET_KEY

    checkout_session = stripe.checkout.Session.create(
        customer_email = order.email,
        payment_method_types=['card'],
        line_items = [
            {
                'price_data': {
                    'currency': 'USD',
                    'product_data': {
                        'name': order.full_name
                    },
                    'unit_amount': int(order.price * 100)
                },
                'quantity': 1
            }
        ],
        mode = 'payment',
        success_url = request.build_absolute_uri(reverse("core:payment-completed", args=[order.oid])) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url = request.build_absolute_uri(reverse("core:payment-completed", args=[order.oid]))
    )

    order.paid_status = False
    order.stripe_payment_intent = checkout_session['id']
    order.save()

    print("checkkout session", checkout_session)
    return JsonResponse({"sessionId": checkout_session.id})


@login_required
def apply_coupon_view(request):
    if request.method == "POST":
        try:
            code = request.POST.get("code")
            order_id = request.POST.get("order_id")
            
            try:
                order = CartOrder.objects.get(oid=order_id, user=request.user)
                original_price = order.price + order.saved  # Get original price before any discounts
            except CartOrder.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Order not found'
                })
            
            try:
                coupon = Coupon.objects.get(code=code)
            except Coupon.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid coupon code'
                })

            # Basic validation checks
            if not coupon.active:
                return JsonResponse({
                    'status': 'error',
                    'message': 'This coupon is no longer active'
                })

            if coupon.expiry_date and timezone.now() > coupon.expiry_date:
                return JsonResponse({
                    'status': 'error',
                    'message': 'This coupon has expired'
                })

            if coupon.times_used >= coupon.usage_limit:
                return JsonResponse({
                    'status': 'error',
                    'message': 'This coupon has reached its usage limit'
                })

            # Check if this specific coupon has been applied to this order
            if coupon in order.coupons.all():
                return JsonResponse({
                    'status': 'error',
                    'message': 'This coupon has already been applied'
                })
            
            # Calculate percentage discount based on original price
            discount_percentage = Decimal(str(coupon.discount))
            discount_amount = (original_price * discount_percentage) / Decimal('100')
            discount_amount = discount_amount.quantize(Decimal('0.01'))
            
            # Calculate new price and total saved
            new_total_saved = order.saved + discount_amount
            new_price = original_price - new_total_saved
            
            # Update order
            order.coupons.add(coupon)
            order.price = new_price
            order.saved = new_total_saved
            order.save()

            # Increment coupon usage counter
            coupon.times_used += 1
            coupon.save()

            # Get all applied coupons info for display
            applied_coupons = []
            total_discount_percentage = 0
            for applied_coupon in order.coupons.all():
                applied_coupons.append({
                    'code': applied_coupon.code,
                    'discount': applied_coupon.discount
                })
                total_discount_percentage += applied_coupon.discount
            
            return JsonResponse({
                'status': 'success',
                'message': f'Coupon applied! {coupon.discount}% off - Additional Ksh{discount_amount:.2f} has been deducted',
                'subtotal': float(original_price),
                'new_price': float(new_price),
                'total_saved': float(new_total_saved),
                'current_discount': float(discount_amount),
                'total_discount_percentage': float(total_discount_percentage),
                'applied_coupons': applied_coupons
            })
                
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })
    
    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })


# @login_required
# def checkout(request, oid):
#     try:
#         order = CartOrder.objects.get(oid=oid, user=request.user)
#         order_items = CartOrderProducts.objects.filter(order=order)
        
#         context = {
#             "order": order,
#             "order_items": order_items,
#             "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,
#         }
#         return render(request, "core/checkout.html", context)
        
#     except CartOrder.DoesNotExist:
#         messages.error(request, "Order not found")
#         return redirect("core:index")


# @login_required
# def payment_completed_view(request, oid):
#     order = CartOrder.objects.get(oid=oid)
    
#     if order.paid_status == False:
#         order.paid_status = True
#         order.save()
        
#     context = {
#         "order": order,
#         "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,

#     }
#     return render(request, 'core/payment-completed.html',  context)


# @login_required
# def payment_failed_view(request):
#     return render(request, 'core/payment-failed.html')



@login_required
def checkout(request, oid):
    try:
        order = get_object_or_404(CartOrder, oid=oid, user=request.user)
        order_items = CartOrderProducts.objects.filter(order=order)
        context = {
            "order": order,
            "order_items": order_items,
            "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,
        }
        return render(request, "core/checkout.html", context)
    except CartOrder.DoesNotExist:
        messages.error(request, "Order not found")
        return redirect("core:index")
    

# New helper function to clear cart
def clear_cart(request):
    """Helper function to clear the cart session data"""
    request.session['cart_data_obj'] = {}
    request.session.modified = True



def update_product_stock(request, order):
    """Helper function to update product stock"""
    cart = request.session.get('cart', {})
    
    for product_id, quantity in cart.items():
        try:
            product = Product.objects.get(pid=product_id)
            if product.stock_count.isdigit():
                new_stock = int(product.stock_count) - int(quantity)
                product.stock_count = str(max(0, new_stock))
                product.save()
        except Product.DoesNotExist:
            continue

@login_required
def process_payment(request):
    if request.method == 'POST':
        oid = request.POST.get('oid')
        payment_method = request.POST.get('payment_method')

        try:
            order = get_object_or_404(CartOrder, oid=oid, user=request.user)
            cart = request.session.get('cart', {})

            if payment_method == 'stripe':
                # Store cart data before clearing session
                order.cart_data = cart
                order.paid_status = True
                order.save()

                # Update stock immediately
                update_product_stock(request, order)
                
                # Clear session cart
                clear_cart(request)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Payment for order {order.oid} successful', 
                    'redirect': '/',
                    'cart_count': 0
                })

            elif payment_method == 'mpesa':
                # Store cart data before clearing session
                order.cart_data = cart
                order.paid_status = True
                order.save()

                # Update stock immediately
                update_product_stock(request, order)
                
                # Clear session cart
                clear_cart(request)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Payment for order {order.oid} successful', 
                    'redirect': '/',
                    'cart_count': 0
                })

            elif payment_method == 'cash':
                # Store cart data for later use
                order.cart_data = cart
                order.paid_status = False
                order.save()
                
                # Clear session cart
                clear_cart(request)
                
                return JsonResponse({
                    'success': True, 
                    'message': f'Order {order.oid} placed successfully', 
                    'redirect': '/',
                    'cart_count': 0
                })

        except CartOrder.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Order not found'})

    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def customer_dashboard(request):
    # Get or create user profile
    user_profile, created = Profile.objects.get_or_create(user=request.user)

    # Handle profile form submission
    if request.method == "POST":
        if 'profile_update' in request.POST:
            # Handle profile update
            form = ProfileForm(request.POST, request.FILES, instance=user_profile)
            if form.is_valid():
                form.save()
                messages.success(request, "Profile Updated Successfully.")
                return redirect("core:dashboard")
        else:
            # Handle address creation
            address = request.POST.get("address")
            mobile = request.POST.get("mobile")
            if address and mobile:
                Address.objects.create(
                    user=request.user,
                    address=address,
                    mobile=mobile,
                )
                messages.success(request, "Address Added Successfully.")
                return redirect("core:dashboard")
            else:
                messages.error(request, "Please fill all fields.")

    # Get orders data
    orders_list = CartOrder.objects.filter(user=request.user).order_by("-id")
    address = Address.objects.filter(user=request.user)

    # Enhanced monthly order statistics with better organization
    current_year = timezone.now().year
    monthly_orders = CartOrder.objects.filter(
        user=request.user,
        order_date__year=current_year
    ).annotate(
        month=ExtractMonth("order_date")
    ).values("month").annotate(
        count=Count("id")
    ).order_by("month")

    # Initialize all months with zero counts for complete yearly data
    month_data = {i: 0 for i in range(1, 13)}
    
    # Update with actual counts
    for order in monthly_orders:
        month_data[order['month']] = order['count']

    # Prepare chart data
    month = [calendar.month_name[i] for i in range(1, 13)]  # All months
    total_orders = list(month_data.values())

    # Get additional statistics for the dashboard
    stats = {
        'total_orders': orders_list.count(),
        'this_month': orders_list.filter(order_date__month=timezone.now().month).count(),
        'last_order_date': orders_list.first().order_date if orders_list.exists() else None,
    }

    # Initialize profile form
    profile_form = ProfileForm(instance=user_profile)

    context = {
        "user_profile": user_profile,
        "profile_form": profile_form,
        "orders": monthly_orders,
        "orders_list": orders_list,
        "address": address,
        "month": month,
        "total_orders": total_orders,
        "stats": stats,
    }
    return render(request, 'core/dashboard.html', context)



def order_detail(request, id):
    order = CartOrder.objects.get(user=request.user, id=id)
    order_items = CartOrderProducts.objects.filter(order=order)

    
    context = {
        "order_items": order_items,
    }
    return render(request, 'core/order-detail.html', context)


def make_address_default(request):
    id = request.GET['id']
    Address.objects.update(status=False)
    Address.objects.filter(id=id).update(status=True)
    return JsonResponse({"boolean": True})


@login_required
def wishlist_view(request):
    # Filter wishlist items for the logged-in user
    wishlist = wishlist_model.objects.filter(user=request.user)
    
    # Count the number of items in the user's wishlist
    wishlist_count = wishlist.count()
    
    context = {
        "w": wishlist,
        "wishlist_count": wishlist_count,
    }
    return render(request, "core/wishlist.html", context)



@login_required
def add_to_wishlist(request):
    if request.method == 'GET':
        try:
            wishlist_data = {}
            product_id = request.GET['id']
            
            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Product not found'
                })

            # Check if in wishlist
            wishlist_item = wishlist_model.objects.filter(
                product=product,
                user=request.user
            )

            if wishlist_item.exists():
                # Item already exists in wishlist
                is_added = False
                message = f"{request.GET.get('title', 'Item')} already exists in wishlist"
            else:
                # Add to wishlist
                wishlist_model.objects.create(
                    user=request.user,
                    product=product
                )
                is_added = True
                message = f"{request.GET.get('title', 'Item')} added to wishlist"

            # Get total wishlist items
            total_items = wishlist_model.objects.filter(user=request.user).count()

            return JsonResponse({
                'status': 'success',
                'message': message,
                'is_added': is_added,
                'totalwishlistitems': total_items
            })

        except Exception as e:
            print(f"Wishlist Error: {str(e)}")  # Debug print
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            })

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    })


@login_required
@require_http_methods(["POST"])
def remove_wishlist(request):
    try:
        wishlist_id = request.POST.get('wishlist_id')
        if not wishlist_id:
            return JsonResponse({
                'status': 'error',
                'message': 'No wishlist ID provided'
            })

        wishlist_item = get_object_or_404(wishlist_model, 
                                        id=wishlist_id, 
                                        user=request.user)
        product_title = wishlist_item.product.title
        wishlist_item.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'{product_title} has been removed from your wishlist',
            'wishlist_id': wishlist_id
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        })






# Other Pages 
def contact(request):
    return render(request, "core/contact.html")


def ajax_contact_form(request):
    full_name = request.GET['full_name']
    email = request.GET['email']
    phone = request.GET['phone']
    subject = request.GET['subject']
    message = request.GET['message']

    contact = ContactUs.objects.create(
        full_name=full_name,
        email=email,
        phone=phone,
        subject=subject,
        message=message,
    )

    data = {
        "bool": True,
        "message": "Message Sent Successfully"
    }

    return JsonResponse({"data":data})


def about_us(request):
    return render(request, "core/about_us.html")


def purchase_guide(request):
    return render(request, "core/purchase_guide.html")

def privacy_policy(request):
    return render(request, "core/privacy_policy.html")

def terms_of_service(request):
    return render(request, "core/terms_of_service.html")




@login_required
def my_orders_view(request):
    orders = CartOrder.objects.filter(user=request.user).order_by('-order_date')
    return render(request, 'core/my_orders.html', {'orders': orders})



def order_tracking_view(request):
    return render(request, "core/order_tracking.html")



@login_required
def cancel_order(request, order_id):
    if request.method == 'POST':
        try:
            order = CartOrder.objects.get(oid=order_id, user=request.user)
            if order.product_status not in ['delivered', 'cancelled']:
                order.product_status = 'cancelled'
                order.save()
                return JsonResponse({'success': True})
            return JsonResponse({
                'success': False,
                'message': 'Cannot cancel this order'
            })
        except CartOrder.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Order not found'
            })
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
def contact_support(request):
    if request.method == 'POST':
        # Handle support request
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'Invalid request'})



def track_order_ajax(request):
    if request.method == 'GET':
        order_id = request.GET.get('order_id')
        try:
            order = CartOrder.objects.get(oid=order_id)
            
            response_data = {
                'status': 'success',
                'order_data': {
                    'oid': order.oid,
                    'date': order.order_date.strftime("%B %d, %Y"),
                    'status': order.product_status,
                    'paid_status': order.paid_status,
                    'price': float(order.price),
                    'tracking_id': order.tracking_id or 'Not available',
                }
            }
            return JsonResponse(response_data)
        except CartOrder.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Order not found'
            })
    return JsonResponse({'status': 'error', 'message': 'Invalid request'})



def hot_deals_view(request):
    return render(request, "core/hot_deals.html")


def new_arrivals_view(request):
    return render(request, "core/new_arrivals.html")



@login_required
def get_shipping_addresses(request):
    """Get saved shipping addresses for the logged-in user."""
    addresses = ShippingAddress.objects.filter(user=request.user)
    addresses_data = list(addresses.values('id', 'full_name', 'phone', 'email', 'address', 'city', 'is_default'))
    return JsonResponse({'addresses': addresses_data})



@login_required
def save_shipping_address(request):
    """Save or update a shipping address via AJAX."""
    if request.method == "POST":
        address_id = request.POST.get('address_id')
        address_data = {
            'user': request.user,
            'full_name': request.POST.get('full_name'),
            'phone': request.POST.get('phone'),
            'email': request.POST.get('email'),
            'address': request.POST.get('address'),
            'city': request.POST.get('city'),
            'is_default': request.POST.get('is_default') == 'true'
        }

        try:
            if address_data['is_default']:
                ShippingAddress.objects.filter(user=request.user).update(is_default=False)

            if address_id:
                # Update existing address
                address = ShippingAddress.objects.get(id=address_id, user=request.user)
                for key, value in address_data.items():
                    if key != 'user':
                        setattr(address, key, value)
                address.save()
            else:
                # Create new address
                address = ShippingAddress.objects.create(**address_data)

            return JsonResponse({'status': 'success', 'address_id': address.id})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    return JsonResponse({'status': 'error'}, status=400)


# @login_required
# def save_checkout_info(request):
#     """Save checkout information with the selected shipping address."""
#     if request.method == "POST":
#         address_id = request.POST.get('address_id')
#         try:
#             shipping_address = ShippingAddress.objects.get(id=address_id, user=request.user)
#         except ShippingAddress.DoesNotExist:
#             return JsonResponse({
#                 'status': 'error',
#                 'message': 'Invalid shipping address'
#             }, status=400)

#         cart_total_amount = 0
#         if 'cart_data_obj' in request.session:
#             for p_id, item in request.session['cart_data_obj'].items():
#                 cart_total_amount += int(item['qty']) * float(item['price'])
            
#             # Create order
#             order = CartOrder.objects.create(
#                 user=request.user,
#                 price=cart_total_amount,
#                 full_name=shipping_address.full_name,
#                 email=shipping_address.email,
#                 phone=shipping_address.phone,
#                 address=shipping_address.address,
#                 city=shipping_address.city,
#             )
            
#             # Create order products
#             for p_id, item in request.session['cart_data_obj'].items():
#                 CartOrderProducts.objects.create(
#                     order=order,
#                     invoice_no=f"INVOICE_NO-{order.id}",
#                     item=item['title'],
#                     image=item['image'],
#                     qty=item['qty'],
#                     price=item['price'],
#                     total=float(item['qty']) * float(item['price'])
#                 )

#             # Clear cart session
#             del request.session['cart_data_obj']
#             request.session.modified = True

#             return JsonResponse({
#                 'status': 'success',
#                 'order_id': order.id,
#                 'redirect_url': f'/checkout/{order.id}/'
#             })

#     return JsonResponse({'status': 'error'}, status=400)