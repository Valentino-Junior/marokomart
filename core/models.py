from django.db import models
from shortuuid.django_fields import ShortUUIDField
from django.utils.html import mark_safe
from userauths.models import User
from taggit.managers import TaggableManager
from django_ckeditor_5.fields import CKEditor5Field
from django.utils import timezone
from django.core.validators import MinValueValidator
import random
import string

STATUS_CHOICE = (
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )


STATUS = (
    ("disabled", "Disabled"),
    ("in_review", "In Review"),
    ("published", "Published"),
)


RATING = (
    (1,  "★☆☆☆☆"),
    (2,  "★★☆☆☆"),
    (3,  "★★★☆☆"),
    (4,  "★★★★☆"),
    (5,  "★★★★★"),
)


def user_directory_path(instance, filename):
    return 'user_{0}/{1}'.format(instance.user.id, filename)


class Category(models.Model):
    cid = ShortUUIDField(unique=True, length=10, max_length=20,
                         prefix="cat", alphabet="abcdefgh12345")
    title = models.CharField(max_length=100, default="Food")
    image = models.ImageField(upload_to="category", default="category.jpg")

    class Meta:
        verbose_name_plural = "Categories"

    def category_image(self):
        return mark_safe('<img src="%s" width="50" height="50" />' % (self.image.url))

    def product_count(self):
        return Product.objects.filter(category=self).count()

    def __str__(self):
        return self.title




class Product(models.Model):
    pid = ShortUUIDField(unique=True, length=10,
                         max_length=20, alphabet="abcdefgh12345")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name="category")

    title = models.CharField(max_length=100, default="Fresh Pear")
    image = models.ImageField(
        upload_to=user_directory_path, default="product.jpg")
    
    description = CKEditor5Field(config_name='extends', null=True, blank=True)

    buying_price = models.DecimalField(
        max_digits=12, decimal_places=2, default="0.00", validators=[MinValueValidator(0)])

    price = models.DecimalField(
        max_digits=12, decimal_places=2, default="0.00", validators=[MinValueValidator(0)])
    old_price = models.DecimalField(
        max_digits=12, decimal_places=2, default="0.00", validators=[MinValueValidator(0)])

    stock_count = models.CharField(max_length=100, default="0", null=True, blank=True)
    low_stock_threshold = models.IntegerField(default=5) 

    product_status = models.CharField(
        choices=STATUS, max_length=10, default="published")

    status = models.BooleanField(default=True)
    in_stock = models.BooleanField(default=True)
    
    sku = ShortUUIDField(unique=True, length=4, max_length=10,
                         prefix="sku", alphabet="1234567890")

    date = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(null=True, blank=True)


    # New fields
    is_special_offer = models.BooleanField(default=False)
    special_offer_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    special_offer_ends = models.DateTimeField(null=True, blank=True)
    
    is_new_arrival = models.BooleanField(default=False)
    new_arrival_ends = models.DateTimeField(null=True, blank=True)
    
    
    

    class Meta:
        verbose_name_plural = "Products"
        ordering = ['-date'] 

    def has_active_offer(self):
        return self.is_special_offer and self.special_offer_ends and self.special_offer_ends > timezone.now()
    
    def get_special_offer_percentage(self):
        if self.is_special_offer and self.special_offer_price:
            discount = self.price - self.special_offer_price
            percentage = (discount / self.price) * 100
            return round(percentage)
        return 0

    def product_image(self):
        return mark_safe('<img src="%s" width="50" height="50" />' % (self.image.url))

    def __str__(self):
        return self.title

    def get_precentage(self):
        new_price = (self.price / self.old_price) * 100
        return new_price
    

    def check_low_stock(self):
        """Check if product is low in stock"""
        try:
            current_stock = int(self.stock_count)
            return current_stock <= self.low_stock_threshold
        except ValueError:
            return False

    
    def get_actual_price(self):
        if self.is_special_offer and self.special_offer_ends > timezone.now():
            return self.special_offer_price
        return self.price
    
        

    def save(self, *args, **kwargs):
        # Check if stock count changed and create alert if needed
        if self.pk:
            old_product = Product.objects.get(pk=self.pk)
            if self.stock_count != old_product.stock_count:
                try:
                    current_stock = int(self.stock_count)
                    if current_stock <= self.low_stock_threshold:
                        LowStockAlert.objects.create(
                            product=self,
                            current_stock=current_stock,
                            threshold=self.low_stock_threshold
                        )
                except ValueError:
                    pass
        super().save(*args, **kwargs)




class ProductImages(models.Model):
    images = models.ImageField(
        upload_to="product-images", default="product.jpg")
    product = models.ForeignKey(
        Product, related_name="p_images", on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Product Images"



class LowStockAlert(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    current_stock = models.IntegerField()
    threshold = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_viewed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Low Stock Alert: {self.product.title} ({self.current_stock} remaining)"




class ShippingAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=100)
    email = models.EmailField()
    region = models.CharField(
        max_length=100,
        help_text="Town or city name"
    )
    is_default = models.BooleanField(default=False)
    date_added = models.DateTimeField(auto_now_add=True)
    shipping_instructions = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Special instructions for delivery (optional)"
    )

    class Meta:
        verbose_name_plural = "Shipping Addresses"
        ordering = ['-is_default', '-date_added']

    def __str__(self):
        return f"{self.full_name} - {self.region}"

    def save(self, *args, **kwargs):
        if self.is_default:
            # Set all other addresses of this user to non-default
            ShippingAddress.objects.filter(user=self.user).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


############################################## Cart, Order, OrderITems and Address ##################################
############################################## Cart, Order, OrderITems and Address ##################################
############################################## Cart, Order, OrderITems and Address ##################################
############################################## Cart, Order, OrderITems and Address ##################################


class CartOrder(models.Model):
    
    PAYMENT_METHOD_CHOICES = (
        ('stripe', 'Stripe'),
        ('mpesa', 'M-Pesa'),
        ('cash', 'Cash on Delivery')
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.SET_NULL, null=True)
    cart_data = models.JSONField(null=True, blank=True)  # Add this field

    price = models.DecimalField(max_digits=12, decimal_places=2, default="0.00")
    saved = models.DecimalField(max_digits=12, decimal_places=2, default="0.00")
    coupons = models.ManyToManyField("core.Coupon", blank=True)
    tracking_id = models.CharField(max_length=100, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, null=True)
    external_reference = models.CharField(max_length=100, null=True, blank=True)
    mpesa_receipt = models.CharField(max_length=100, null=True, blank=True)

    paid_status = models.BooleanField(default=False)
    order_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    product_status = models.CharField(choices=STATUS_CHOICE, max_length=30, default="processing")
    sku = ShortUUIDField(null=True, blank=True, length=5,prefix="SKU", max_length=20, alphabet="1234567890")
    oid = ShortUUIDField(null=True, blank=True, length=8, max_length=20, alphabet="1234567890")
    stripe_payment_intent = models.CharField(max_length=1000, null=True, blank=True)
    date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    is_viewed = models.BooleanField(default=False)


    @classmethod
    def get_unread_count(cls):
        return cls.objects.filter(is_viewed=False).count()
    
    class Meta:
        verbose_name_plural = "Cart Order"
        ordering = ["-order_date"]

    def save(self, *args, **kwargs):
        if self.pk:
            old_order = CartOrder.objects.get(pk=self.pk)
            # If payment status changed to True (for cash payments)
            if not old_order.paid_status and self.paid_status and self.cart_data:
                # Update stock using stored cart data
                for product_id, quantity in self.cart_data.items():
                    try:
                        product = Product.objects.get(pid=product_id)
                        if product.stock_count.isdigit():
                            new_stock = int(product.stock_count) - int(quantity)
                            product.stock_count = str(max(0, new_stock))
                            product.save()
                    except Product.DoesNotExist:
                        continue
        super().save(*args, **kwargs)


class CartOrderProducts(models.Model):
    order = models.ForeignKey(CartOrder, on_delete=models.CASCADE)
    invoice_no = models.CharField(max_length=200)
    product_status = models.CharField(max_length=200)
    item = models.CharField(max_length=200)
    image = models.CharField(max_length=200)
    qty = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=12, decimal_places=2, default="0.00")
    total = models.DecimalField(max_digits=12, decimal_places=2, default="0.00")

    class Meta:
        verbose_name_plural = "Cart Order Items"

    def order_img(self):
        return mark_safe('<img src="/media/%s" width="50" height="50" />' % (self.image))


############################################## Product Revew, wishlists, Address ##################################
############################################## Product Revew, wishlists, Address ##################################
############################################## Product Revew, wishlists, Address ##################################
############################################## Product Revew, wishlists, Address ##################################


class ProductReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="reviews")
    review = models.TextField()
    rating = models.IntegerField(choices=RATING, default=None)
    is_viewed = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    

    @classmethod
    def get_unread_count(cls):
        return cls.objects.filter(is_viewed=False).count()

    class Meta:
        verbose_name_plural = "Product Reviews"
        ordering = ['-date']

    def __str__(self):
        return f"Review for {self.product.title if self.product else 'Unknown Product'}"

    def get_rating(self):
        return self.rating


class wishlist_model(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "wishlists"

    def __str__(self):
        return self.product.title


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    mobile = models.CharField(max_length=300, null=True)
    address = models.CharField(max_length=100, null=True)

    class Meta:
        verbose_name_plural = "Address"


class Coupon(models.Model):
    code = models.CharField(max_length=1000, unique=True)
    discount = models.IntegerField(default=1)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    usage_limit = models.IntegerField(default=1)  # How many times the coupon can be used
    times_used = models.IntegerField(default=0)   # Track how many times it's been used
    
    def is_valid(self):
        if not self.active:
            return False, "This coupon is inactive"
        if self.expiry_date and timezone.now() > self.expiry_date:
            return False, "This coupon has expired"
        if self.times_used >= self.usage_limit:
            return False, "This coupon has reached its usage limit"
        return True, "Valid coupon"

    @staticmethod
    def generate_code():
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            if not Coupon.objects.filter(code=code).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} ({self.discount}% off)"
    



class Order_Review(models.Model):
    RATING_CHOICES = (
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(CartOrder, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=RATING_CHOICES)
    comment = models.TextField()
    is_viewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @classmethod
    def get_unread_count(cls):
        return cls.objects.filter(is_viewed=False).count()

    class Meta:
        unique_together = ('user', 'order')  # One review per order

    def __str__(self):
        return f"Review for Order {self.order.oid} by {self.user.username}"



        
class SupportTicket(models.Model):
    ISSUE_CHOICES = (
        ('delivery', 'Delivery Issue'),
        ('product', 'Product Issue'),
        ('payment', 'Payment Issue'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey(CartOrder, on_delete=models.CASCADE)
    issue_type = models.CharField(max_length=20, choices=ISSUE_CHOICES)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    is_viewed = models.BooleanField(default=False)
    admin_response = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    @classmethod
    def get_unread_count(cls):
        return cls.objects.filter(is_viewed=False).count()


    def __str__(self):
        return f"Support Ticket #{self.id} - {self.order.oid}"

    class Meta:
        ordering = ['-created_at']
    



class PayHeroPayment(models.Model):
    PAYMENT_STATUS = (
        ('PENDING', 'Payment Pending'),
        ('SUCCESS', 'Payment Successful'),
        ('FAILED', 'Payment Failed'), 
        ('CANCELLED', 'Payment Cancelled')
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    shipping_address = models.ForeignKey(ShippingAddress, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15) 
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    external_reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='PENDING')
    cart_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} - {self.status}" 