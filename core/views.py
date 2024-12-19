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


import uuid



# views.py
def index(request):
   # Get current time for checking active offers and new arrivals
   now = timezone.now()
   
   # Get active special offers and new arrivals
   special_offers = Product.objects.filter(
       product_status="published",
       is_special_offer=True,
       special_offer_ends__gt=now
   )

   new_arrivals = Product.objects.filter(
       product_status="published", 
       is_new_arrival=True,
       new_arrival_ends__gt=now
   )

   # Combine and remove duplicates
   featured_products = list(special_offers) + list(new_arrivals)
   featured_products = list(dict.fromkeys(featured_products))  # Remove duplicates

   sort_by = request.GET.get('sort_by', '')
   
   # Apply sorting
   if sort_by == 'price_low_high':
       featured_products.sort(key=lambda x: x.get_actual_price())
   elif sort_by == 'price_high_low':
       featured_products.sort(key=lambda x: x.get_actual_price(), reverse=True)
   else:
       featured_products.sort(key=lambda x: x.id, reverse=True)
   
   context = {
       "products": featured_products,
       "current_sort": sort_by,
       "now": now,
       "special_offers_count": special_offers.count(),
       "new_arrivals_count": new_arrivals.count()
   }
   
   if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
       best_deal_html = render_to_string(
           'core/includes/best_deal.html',
           context,
           request=request
       )
       return JsonResponse({
           'product_grid': best_deal_html,
           'product_count': len(featured_products),
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
    query = request.GET.get("q", "")
    category_id = request.GET.get("category", "")

    products = Product.objects.all()

    # Filter by search query if provided
    if query:
        products = products.filter(title__icontains=query)

    # Filter by category if selected
    if category_id:
        products = products.filter(category__cid=category_id)

    # Get all categories for the dropdown
    categories = Category.objects.all()

    # Get the selected category for display
    selected_category = None
    if category_id:
        selected_category = Category.objects.filter(cid=category_id).first()

    context = {
        "products": products.order_by("-date"),
        "query": query,
        "categories": categories,
        "selected_category": selected_category,
        "current_category": category_id,
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
            quantity = int(request.GET.get('quantity', '1'))
            
            # Get the product instance and its current price
            product = Product.objects.get(pid=request.GET['pid'])
            current_price = product.get_actual_price()
            
            cart_product[str(product_id)] = {
                'title': request.GET['title'],
                'qty': str(quantity),
                'price': str(current_price),  # Use the actual price from get_actual_price
                'image': request.GET['image'],
                'pid': request.GET['pid'],
                'is_special_offer': product.is_special_offer and product.special_offer_ends > timezone.now(),
                'original_price': str(product.price),  # Store original price for reference
            }

            if 'cart_data_obj' in request.session:
                if str(product_id) in request.session['cart_data_obj']:
                    cart_data = request.session['cart_data_obj']
                    # Add the new quantity to existing quantity
                    cart_data[str(product_id)]['qty'] = str(
                        int(cart_data[str(product_id)]['qty']) + quantity
                    )
                    # Update price in case offer status has changed
                    cart_data[str(product_id)]['price'] = str(current_price)
                    cart_data[str(product_id)]['is_special_offer'] = product.is_special_offer and product.special_offer_ends > timezone.now()
                    request.session['cart_data_obj'] = cart_data
                else:
                    cart_data = request.session['cart_data_obj']
                    cart_data.update(cart_product)
                    request.session['cart_data_obj'] = cart_data
            else:
                request.session['cart_data_obj'] = cart_product
            
            request.session.modified = True
            
            # Calculate subtotal
            cart_data = request.session['cart_data_obj']
            for item_id, item_data in cart_data.items():
                item_data['subtotal'] = str(float(item_data['qty']) * float(item_data['price']))
            
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
            cart_total = Decimal(request.POST.get("cart_total", "0"))
            
            try:
                coupon = Coupon.objects.get(code=code)
            except Coupon.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid coupon code'
                })

            # Validate coupon
            is_valid, message = coupon.is_valid()
            if not is_valid:
                return JsonResponse({
                    'status': 'error',
                    'message': message
                })

            # Get or initialize coupon session data
            coupon_data = request.session.get('coupon_data', {
                'applied_coupons': [],
                'total_saved': "0.00",
                'final_total': str(cart_total)
            })

            # Check if already applied
            if any(c['code'] == code for c in coupon_data['applied_coupons']):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Coupon already applied'
                })

            # Calculate discount
            discount_amount = (cart_total * Decimal(str(coupon.discount))) / Decimal('100')
            total_saved = Decimal(coupon_data['total_saved']) + discount_amount
            final_total = cart_total - total_saved

            # Update coupon data
            coupon_data['applied_coupons'].append({
                'code': coupon.code,
                'discount': coupon.discount
            })
            coupon_data['total_saved'] = str(total_saved)
            coupon_data['final_total'] = str(final_total)
            
            # Save to session
            request.session['coupon_data'] = coupon_data
            
            return JsonResponse({
                'status': 'success',
                'message': f'Coupon applied! {coupon.discount}% off - Additional Ksh{discount_amount:.2f} has been deducted',
                'subtotal': float(cart_total),
                'new_price': float(final_total),
                'total_saved': float(total_saved),
                'applied_coupons': coupon_data['applied_coupons']
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



@login_required
def redirect_to_checkout(request):
    if 'cart_data_obj' in request.session:
        # Generate a temporary unique identifier for checkout
        temp_oid = f"TEMP_{uuid.uuid4().hex[:10]}"
        return redirect("core:checkout", oid=temp_oid)
    return redirect("core:cart")


@login_required
def checkout(request, oid):
    cart_data = request.session.get('cart_data_obj', {})
    
    if not cart_data:
        messages.error(request, "Your cart is empty")
        return redirect("core:cart")

    # Calculate cart totals from session data
    cart_items = []
    cart_total = 0
    for product_id, item in cart_data.items():
        subtotal = float(item['qty']) * float(item['price'])
        cart_items.append({
            'item': item['title'],
            'image': item['image'],
            'qty': item['qty'],
            'price': item['price'],
            'total': subtotal
        })
        cart_total += subtotal

    # Get shipping addresses
    shipping_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-date_added')
    
    # Get coupon data from session if exists
    coupon_data = request.session.get('coupon_data', {
        'applied_coupons': [],
        'total_discount': 0,
        'final_total': cart_total
    })

    context = {
        "oid": oid,
        "order_items": cart_items,
        "cart_total": cart_total,
        "shipping_addresses": shipping_addresses,
        "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,
        "coupon_data": coupon_data,
    }
    
    return render(request, "core/checkout.html", context)

    

# New helper function to clear cart
def clear_cart(request):
    """Helper function to clear the cart session data"""
    request.session['cart_data_obj'] = {}
    request.session.modified = True



def update_product_stock(request, order):
    # Get all order items for this order
    order_items = CartOrderProducts.objects.filter(order=order)
    
    for order_item in order_items:
        try:
            # Get the product using the item title (assuming this matches product title)
            product = Product.objects.get(title=order_item.item)
            
            # Check if stock is a valid number
            if product.stock_count.isdigit():
                # Calculate new stock
                new_stock = int(product.stock_count) - order_item.qty
                # Ensure stock doesn't go below 0
                product.stock_count = str(max(0, new_stock))
                product.save()
                
        except Product.DoesNotExist:
            continue



@login_required
def process_payment(request):
    if request.method == 'POST':
        shipping_address_id = request.POST.get('shipping_address_id')
        payment_method = request.POST.get('payment_method')
        cart_data = request.session.get('cart_data_obj', {})
        coupon_data = request.session.get('coupon_data', {})

        try:
            if not shipping_address_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Please select a shipping address'
                })

            shipping_address = ShippingAddress.objects.get(
                id=shipping_address_id, 
                user=request.user
            )
            
            # Calculate final price with discounts
            cart_total = sum(int(item['qty']) * Decimal(str(item['price'])) for item in cart_data.values())
            saved_amount = Decimal(coupon_data.get('total_saved', '0'))
            final_total = cart_total - saved_amount

            # Create initial order
            order = CartOrder.objects.create(
                user=request.user,
                shipping_address=shipping_address,
                price=final_total,
                saved=saved_amount,
                cart_data=cart_data,
                payment_method=payment_method
            )

            # Add applied coupons
            for coupon_info in coupon_data.get('applied_coupons', []):
                try:
                    coupon = Coupon.objects.get(code=coupon_info['code'])
                    order.coupons.add(coupon)
                    coupon.times_used += 1
                    coupon.save()
                except Coupon.DoesNotExist:
                    continue

            # Create order items
            for item in cart_data.values():
                CartOrderProducts.objects.create(
                    order=order,
                    invoice_no=f"INVOICE_NO-{order.id}",
                    item=item['title'],
                    image=item['image'],
                    qty=item['qty'],
                    price=item['price'],
                    total=Decimal(str(item['qty'])) * Decimal(str(item['price']))
                )

            # Process payment based on method
            if payment_method == 'stripe':
                return process_stripe_payment(request, order)
            elif payment_method == 'mpesa':
                return process_mpesa_payment(request, order)
            elif payment_method == 'cash':
                return process_cash_payment(request, order)
            else:
                raise ValueError("Invalid payment method")

        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            })

    return JsonResponse({'success': False, 'message': 'Invalid request'})


def process_stripe_payment(request, order):
    try:
        # Here you'll integrate Stripe API
        # For now, simulating successful payment
        order.paid_status = True
        order.save()
        
        update_product_stock(request, order)
        clear_session_data(request)
        
        return JsonResponse({
            'success': True,
            'message': f'Stripe payment for order {order.oid} successful',
            'redirect': '/',
            'cart_count': 0
        })
    except Exception as e:
        order.delete()  # Remove order if payment fails
        return JsonResponse({
            'success': False,
            'message': f'Stripe payment failed: {str(e)}'
        })


def process_mpesa_payment(request, order):
    try:
        # Here you'll integrate M-Pesa API
        # For now, simulating successful payment
        order.paid_status = True
        order.save()
        
        update_product_stock(request, order)
        clear_session_data(request)
        
        return JsonResponse({
            'success': True,
            'message': f'M-Pesa payment for order {order.oid} successful',
            'redirect': '/',
            'cart_count': 0
        })
    except Exception as e:
        order.delete()  # Remove order if payment fails
        return JsonResponse({
            'success': False,
            'message': f'M-Pesa payment failed: {str(e)}'
        })
    

def process_cash_payment(request, order):
    try:
        # Cash on delivery doesn't need payment processing
        order.paid_status = False  # Will be marked as paid upon delivery
        order.save()
        
        clear_session_data(request)
        
        return JsonResponse({
            'success': True,
            'message': f'Order {order.oid} placed successfully for cash on delivery',
            'redirect': '/',
            'cart_count': 0
        })
    except Exception as e:
        order.delete()
        return JsonResponse({
            'success': False,
            'message': f'Failed to place cash order: {str(e)}'
        })

def clear_session_data(request):
    clear_cart(request)
    if 'coupon_data' in request.session:
        del request.session['coupon_data']



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
            # Handle shipping address creation
            full_name = request.POST.get("full_name")
            phone = request.POST.get("phone")
            email = request.POST.get("email") or request.user.email
            address = request.POST.get("address")
            city = request.POST.get("city")

            if all([full_name, phone, address, city]):
                # Create new shipping address
                ShippingAddress.objects.create(
                    user=request.user,
                    full_name=full_name,
                    phone=phone,
                    email=email,
                    address=address,
                    city=city,
                    is_default=not ShippingAddress.objects.filter(user=request.user).exists()  # Make default if first address
                )
                messages.success(request, "Shipping Address Added Successfully.")
                return redirect("core:dashboard")
            else:
                messages.error(request, "Please fill all required fields.")

    # Get orders data
    orders_list = CartOrder.objects.filter(user=request.user).order_by("-id")
    
    # Get shipping addresses
    shipping_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-date_added')

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
        'shipping_addresses': {
            'total': shipping_addresses.count(),
            'has_default': shipping_addresses.filter(is_default=True).exists(),
            'default': shipping_addresses.filter(is_default=True).first()
        }
    }

    # Initialize profile form
    profile_form = ProfileForm(instance=user_profile)

    context = {
        # User and Profile
        "user_profile": user_profile,
        "profile_form": profile_form,
        
        # Orders
        "orders": monthly_orders,
        "orders_list": orders_list,
        
        # Shipping Addresses
        "shipping_addresses": shipping_addresses,
        
        # Chart Data
        "month": month,
        "total_orders": total_orders,
        
        # Statistics
        "stats": stats,
    }
    return render(request, 'core/dashboard.html', context)



@login_required
def make_address_default(request, address_id):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            address = ShippingAddress.objects.get(id=address_id, user=request.user)
            
            # Set the current address as default
            ShippingAddress.objects.filter(user=request.user).update(is_default=False)
            address.is_default = True
            address.save()

            # Get the updated list of shipping addresses
            shipping_addresses = ShippingAddress.objects.filter(user=request.user).order_by('-is_default', '-date_added')
            addresses_data = [
                {
                    'id': addr.id,
                    'full_name': addr.full_name,
                    'region': addr.region,
                    'phone': addr.phone,
                    'email': addr.email,
                    'shipping_instructions': addr.shipping_instructions,
                    'is_default': addr.is_default
                } for addr in shipping_addresses
            ]

            return JsonResponse({
                'status': 'success',
                'message': 'Address set as default successfully.',
                'addresses': addresses_data
            })
        except ShippingAddress.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': 'Address not found.'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)


@login_required
def delete_address(request, address_id):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        try:
            address = ShippingAddress.objects.get(id=address_id, user=request.user)
            was_default = address.is_default
            address.delete()
            
            # If the deleted address was default, make another address default
            if was_default:
                newest_address = ShippingAddress.objects.filter(user=request.user).order_by('-date_added').first()
                if newest_address:
                    newest_address.is_default = True
                    newest_address.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Address deleted successfully.'
            })
        except ShippingAddress.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Address not found.'
            })
    return JsonResponse({'success': False, 'message': 'Invalid request.'})
    
    

def order_detail(request, id):
    order = CartOrder.objects.get(user=request.user, id=id)
    order_items = CartOrderProducts.objects.filter(order=order)

    
    context = {
        "order_items": order_items,
    }
    return render(request, 'core/order-detail.html', context)





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



def special_offers_view(request):
    # Get all active special offers
    special_offers = Product.objects.filter(
        is_special_offer=True,
        special_offer_ends__gt=timezone.now()
    ).select_related('category')  # Optimize database queries
    
    # Calculate savings for each product
    for offer in special_offers:
        offer.saving_amount = offer.price - offer.special_offer_price
        offer.saving_percentage = (offer.saving_amount / offer.price) * 100
    
    # Get offers ending soon (within 24 hours)
    ending_soon = special_offers.filter(
        special_offer_ends__lte=timezone.now() + timezone.timedelta(days=1)
    )
    
    context = {
        'products': special_offers,
        'now': timezone.now(),
        'title': 'Special Offers',
        'product_count': special_offers.count(),
        'ending_soon_count': ending_soon.count(),
        'total_savings': sum(offer.saving_amount for offer in special_offers),
    }
    
    # Add sorting functionality
    sort_by = request.GET.get('sort_by', 'ending_soon')
    
    if sort_by == 'price_low_high':
        special_offers = special_offers.order_by('special_offer_price')
    elif sort_by == 'price_high_low':
        special_offers = special_offers.order_by('-special_offer_price')
    elif sort_by == 'biggest_savings':
        special_offers = sorted(special_offers, key=lambda x: x.saving_percentage, reverse=True)
    else:  # ending_soon
        special_offers = special_offers.order_by('special_offer_ends')
    
    context['products'] = special_offers
    context['sort_by'] = sort_by
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'core/partials/product_grid.html', context)
    
    return render(request, 'core/special_offers.html', context)


def new_arrivals_view(request):
   # Get new arrival products
   new_arrivals = Product.objects.filter(
       is_new_arrival=True,
       new_arrival_ends__gt=timezone.now()
   ).select_related('category').order_by('-date')

   context = {
       'products': new_arrivals,
       'now': timezone.now(),
       'title': 'New Arrivals',
       'product_count': new_arrivals.count()
   }

   # Handle sorting if AJAX request
   if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
       sort_by = request.GET.get('sort_by', '')
       
       if sort_by == 'price_low_high':
           new_arrivals = new_arrivals.order_by('price')
       elif sort_by == 'price_high_low':
           new_arrivals = new_arrivals.order_by('-price')
       elif sort_by == 'oldest':
           new_arrivals = new_arrivals.order_by('date')
       # Default is newest first
       
       context['products'] = new_arrivals
       context['product_count'] = new_arrivals.count()
       
       return render(request, 'core/partials/product_grid.html', context)

   return render(request, 'core/new_arrivals.html', context)



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
        try:
            address_id = request.POST.get('address_id')
            address_data = {
                'user': request.user,
                'full_name': request.POST.get('full_name'),
                'phone': request.POST.get('phone'),
                'email': request.POST.get('email'),
                'region': request.POST.get('region'),
                'shipping_instructions': request.POST.get('shipping_instructions'),
                'is_default': request.POST.get('is_default') == 'true'
            }

            # Validate required fields
            required_fields = ['full_name', 'phone', 'email', 'region']
            for field in required_fields:
                if not address_data.get(field):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'{field.replace("_", " ").title()} is required.'
                    }, status=400)

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

            return JsonResponse({
                'status': 'success',
                'address_id': address.id
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)

    return JsonResponse({
        'status': 'error',
        'message': 'Invalid request method'
    }, status=400)


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