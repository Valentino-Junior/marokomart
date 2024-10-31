
from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from requests import session
import stripe
from taggit.models import Tag
from core.models import Coupon, Product, Category, CartOrder, CartOrderProducts, ProductImages, ProductReview, wishlist_model, Address
from userauths.models import ContactUs, Profile
from core.forms import ProductReviewForm
from django.template.loader import render_to_string
from django.contrib import messages

from django.urls import reverse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from paypal.standard.forms import PayPalPaymentsForm
from django.contrib.auth.decorators import login_required

import calendar
from django.db.models import Count, Avg, FloatField
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


def index(request):
    # bannanas = Product.objects.all().order_by("-id")
    products = Product.objects.filter(product_status="published").order_by("-id")

    context = {
        "products":products
    }

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
    categories = Category.objects.all()

    context = {
        "categories":categories
    }
    return render(request, 'core/category-list.html', context)


def category_product_list__view(request, cid):

    category = Category.objects.get(cid=cid) # food, Cosmetics
    products = Product.objects.filter(product_status="published", category=category)

    context = {
        "category":category,
        "products":products,
    }
    return render(request, "core/category-product-list.html", context)



def product_detail_view(request, pid):
    # Get product or return 404
    product = get_object_or_404(Product, pid=pid)
    
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
            
            cart_product[str(product_id)] = {
                'title': request.GET['title'],
                'qty': request.GET.get('qty', '1'),
                'price': request.GET['price'],
                'image': request.GET['image'],
                'pid': request.GET['pid'],
            }

            if 'cart_data_obj' in request.session:
                if str(product_id) in request.session['cart_data_obj']:
                    cart_data = request.session['cart_data_obj']
                    cart_data[str(product_id)]['qty'] = str(
                        int(cart_data[str(product_id)]['qty']) + 1
                    )
                    request.session['cart_data_obj'] = cart_data
                else:
                    cart_data = request.session['cart_data_obj']
                    cart_data.update(cart_product)
                    request.session['cart_data_obj'] = cart_data
            else:
                request.session['cart_data_obj'] = cart_product
            
            request.session.modified = True
            
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


def cart_view(request):
    try:
        cart_total_amount = 0
        if 'cart_data_obj' in request.session:
            for p_id, item in request.session['cart_data_obj'].items():
                try:
                    qty = int(item.get('qty', 0))
                    price = float(item.get('price', 0))
                    cart_total_amount += qty * price
                except (ValueError, TypeError):
                    continue
            
            return render(request, "core/cart.html", {
                "cart_data": request.session['cart_data_obj'],
                'totalcartitems': len(request.session['cart_data_obj']),
                'cart_total_amount': cart_total_amount
            })
        
        messages.warning(request, "Your cart is empty")
        return redirect("core:index")
        
    except Exception as e:
        print(f"Error in cart_view: {str(e)}")  # Debug print
        messages.error(request, "Error calculating cart total. Please try again.")
        return redirect("core:index")
    
    

def cart_view(request):
    try:
        cart_total_amount = 0
        cart_data = request.session.get('cart_data_obj', {})
        
        if cart_data:
            print("Current cart data:", cart_data)  # Debug print
            
            for p_id, item in cart_data.items():
                try:
                    # Get quantity
                    qty = item.get('qty', '1')
                    qty = int(str(qty).strip())
                    
                    # Get price
                    price = item.get('price', '0')
                    print(f"Processing item {p_id} - Price: {price}, Qty: {qty}")  # Debug print
                    
                    # Clean price
                    price = str(price).replace('$', '').replace(',', '').strip()
                    price = float(price)
                    
                    # Calculate subtotal
                    subtotal = qty * price
                    cart_total_amount += subtotal
                    
                    # Update item in cart with cleaned values
                    cart_data[p_id]['qty'] = str(qty)
                    cart_data[p_id]['price'] = str(price)
                    cart_data[p_id]['subtotal'] = subtotal
                    
                except (ValueError, TypeError) as e:
                    print(f"Error processing item {p_id}: {str(e)}")  # Debug print
                    continue
            
            # Update session with cleaned data
            request.session['cart_data_obj'] = cart_data
            print(f"Cart total amount: {cart_total_amount}")  # Debug print
            
            context = {
                "cart_data": cart_data,
                'totalcartitems': len(cart_data),
                'cart_total_amount': cart_total_amount
            }
            return render(request, "core/cart.html", context)
        else:
            messages.warning(request, "Your cart is empty")
            return redirect("core:index")
            
    except Exception as e:
        print(f"Cart view error: {str(e)}")  # Debug print
        messages.error(request, "Error calculating cart total. Please try again.")
        return redirect("core:index")
    


def update_cart(request):
    try:
        product_id = str(request.GET['id'])
        product_qty = request.GET['qty']
        cart_data = request.session.get('cart_data_obj', {})
        
        if product_id in cart_data:
            # Update quantity
            try:
                qty = int(str(product_qty).strip())
                if qty < 1:
                    qty = 1
                cart_data[product_id]['qty'] = str(qty)
            except (ValueError, TypeError):
                qty = 1
                cart_data[product_id]['qty'] = '1'
            
            # Recalculate totals
            cart_total_amount = 0
            for pid, item in cart_data.items():
                try:
                    item_qty = int(str(item.get('qty', '1')).strip())
                    item_price = float(str(item.get('price', '0')).replace('$', '').replace(',', '').strip())
                    subtotal = item_qty * item_price
                    cart_data[pid]['subtotal'] = subtotal
                    cart_total_amount += subtotal
                except (ValueError, TypeError):
                    continue
            
            request.session['cart_data_obj'] = cart_data
            
            # Render updated cart
            context = render_to_string("core/async/cart-list.html", {
                "cart_data": cart_data,
                'totalcartitems': len(cart_data),
                'cart_total_amount': cart_total_amount
            })
            
            return JsonResponse({
                "data": context,
                'totalcartitems': len(cart_data)
            })
            
    except Exception as e:
        print(f"Update Cart Error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)

def delete_item_from_cart(request):
    try:
        product_id = str(request.GET['id'])
        cart_data = request.session.get('cart_data_obj', {})
        
        if product_id in cart_data:
            del cart_data[product_id]
            
            # Recalculate totals
            cart_total_amount = 0
            for pid, item in cart_data.items():
                try:
                    qty = int(str(item.get('qty', '1')).strip())
                    price = float(str(item.get('price', '0')).replace('$', '').replace(',', '').strip())
                    subtotal = qty * price
                    cart_data[pid]['subtotal'] = subtotal
                    cart_total_amount += subtotal
                except (ValueError, TypeError):
                    continue
            
            request.session['cart_data_obj'] = cart_data
            
            # Render updated cart
            context = render_to_string("core/async/cart-list.html", {
                "cart_data": cart_data,
                'totalcartitems': len(cart_data),
                'cart_total_amount': cart_total_amount
            })
            
            return JsonResponse({
                "data": context,
                'totalcartitems': len(cart_data)
            })
            
    except Exception as e:
        print(f"Delete Cart Error: {str(e)}")
        return JsonResponse({"error": str(e)}, status=400)
    


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
                full_name=full_name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                state=state,
                country=country,
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
def checkout(request, oid):
    order = CartOrder.objects.get(oid=oid)
    order_items = CartOrderProducts.objects.filter(order=order)

   
    if request.method == "POST":
        code = request.POST.get("code")
        print("code ========", code)
        coupon = Coupon.objects.filter(code=code, active=True).first()
        if coupon:
            if coupon in order.coupons.all():
                messages.warning(request, "Coupon already activated")
                return redirect("core:checkout", order.oid)
            else:
                discount = order.price * coupon.discount / 100 

                order.coupons.add(coupon)
                order.price -= discount
                order.saved += discount
                order.save()

                messages.success(request, "Coupon Activated")
                return redirect("core:checkout", order.oid)
        else:
            messages.error(request, "Coupon Does Not Exists")

        

    context = {
        "order": order,
        "order_items": order_items,
        "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,

    }
    return render(request, "core/checkout.html", context)


@login_required
def payment_completed_view(request, oid):
    order = CartOrder.objects.get(oid=oid)
    
    if order.paid_status == False:
        order.paid_status = True
        order.save()
        
    context = {
        "order": order,
        "stripe_publishable_key": settings.STRIPE_PUBLIC_KEY,

    }
    return render(request, 'core/payment-completed.html',  context)

@login_required
def payment_failed_view(request):
    return render(request, 'core/payment-failed.html')


@login_required
def customer_dashboard(request):
    orders_list = CartOrder.objects.filter(user=request.user).order_by("-id")
    address = Address.objects.filter(user=request.user)


    orders = CartOrder.objects.annotate(month=ExtractMonth("order_date")).values("month").annotate(count=Count("id")).values("month", "count")
    month = []
    total_orders = []

    for i in orders:
        month.append(calendar.month_name[i["month"]])
        total_orders.append(i["count"])

    if request.method == "POST":
        address = request.POST.get("address")
        mobile = request.POST.get("mobile")

        new_address = Address.objects.create(
            user=request.user,
            address=address,
            mobile=mobile,
        )
        messages.success(request, "Address Added Successfully.")
        return redirect("core:dashboard")
    else:
        print("Error")
    
    user_profile = Profile.objects.get(user=request.user)
    print("user profile is: #########################",  user_profile)

    context = {
        "user_profile": user_profile,
        "orders": orders,
        "orders_list": orders_list,
        "address": address,
        "month": month,
        "total_orders": total_orders,
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
    wishlist = wishlist_model.objects.all()
    context = {
        "w":wishlist
    }
    return render(request, "core/wishlist.html", context)


    # w

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
                # Remove from wishlist
                wishlist_item.delete()
                is_added = False
                message = f"{request.GET.get('title', 'Item')} removed from wishlist"
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


def remove_wishlist(request):
    pid = request.GET['id']
    wishlist = wishlist_model.objects.filter(user=request.user)
    wishlist_d = wishlist_model.objects.get(id=pid)
    delete_product = wishlist_d.delete()
    
    context = {
        "bool":True,
        "w":wishlist
    }
    wishlist_json = serializers.serialize('json', wishlist)
    t = render_to_string('core/async/wishlist-list.html', context)
    return JsonResponse({'data':t,'w':wishlist_json})





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



def order_tracking_view(request):
    return render(request, "core/order_tracking.html")


def hot_deals_view(request):
    return render(request, "core/hot_deals.html")


def new_arrivals_view(request):
    return render(request, "core/new_arrivals.html")


