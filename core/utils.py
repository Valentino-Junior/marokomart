import base64
from decimal import Decimal
from .models import Coupon, CouponUsage

class PayHeroConfig:
    @staticmethod
    def generate_auth_token():
        username = "vmb99lVKaTQpHOYyR2Mq"  # Replace with your username
        password = "8iDRZunX6SaPeM8mqS7kOtRKnsZlkSz5EUSpLZjY"
        credentials = f"{username}:{password}"
        return f"Basic {base64.b64encode(credentials.encode()).decode()}"

    @staticmethod
    def get_callback_url(request):
        return f"{request.scheme}://{request.get_host()}/mpesa/callback/"



def process_order_completion(order, request):
    """
    Common function to handle order completion across payment methods
    """
    try:
        # Get coupon data from session
        coupon_data = request.session.get('coupon_data', {})
        
        if coupon_data:
            # Record discount amount
            order.discount_amount = Decimal(coupon_data.get('total_saved', '0.00'))
            order.applied_coupons_data = coupon_data.get('applied_coupons', [])
            
            # If order is paid, record coupon usage and increment usage count
            if order.paid_status:
                for coupon_info in coupon_data.get('applied_coupons', []):
                    try:
                        coupon = Coupon.objects.get(code=coupon_info['code'])
                        
                        # Create coupon usage record
                        CouponUsage.objects.create(
                            user=order.user,
                            coupon=coupon,
                            order=order
                        )
                        
                        # Increment coupon usage count
                        coupon.times_used += 1
                        coupon.save()
                        
                    except Coupon.DoesNotExist:
                        print(f"Coupon {coupon_info['code']} not found")
                    except Exception as e:
                        print(f"Error recording coupon usage: {str(e)}")
            
            order.save()

        # Clear session data
        request.session.pop('cart_data_obj', None)
        request.session.pop('coupon_data', None)
        request.session.modified = True
        
    except Exception as e:
        print(f"Error in process_order_completion: {str(e)}")