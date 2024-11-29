from django.contrib import admin
from .models import Product, LowStockAlert
from core.models import CartOrderProducts, Coupon, Product, Category, CartOrder, ProductImages, ProductReview, wishlist_model, Address, ShippingAddress, LowStockAlert


class ProductImagesAdmin(admin.TabularInline):
    model = ProductImages

class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImagesAdmin]
    list_editable = ['title', 'price', 'product_status', 'low_stock_threshold']
    list_display = ['user', 'title', 'product_image', 'price', 'category', 'product_status', 'pid', 'stock_count', 'low_stock_threshold']

class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_image']


class CartOrderAdmin(admin.ModelAdmin):
    list_editable = ['paid_status', 'product_status', 'sku']
    list_display = ['user',  'price', 'paid_status', 'order_date','product_status', 'sku']


class CartOrderProductsAdmin(admin.ModelAdmin):
    list_display = ['order', 'invoice_no', 'item', 'image','qty', 'price', 'total']


class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'review', 'rating']


class wishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'date']


class AddressAdmin(admin.ModelAdmin):
    list_editable = ['mobile', 'address']
    list_display = ['user', 'mobile', 'address']


class ShippingAddressAdmin(admin.ModelAdmin):
    
    list_display = ['user', 'full_name', 'phone', 'email', 'region', 'shipping_instructions', 'is_default', 'date_added']



class LowStockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'current_stock', 'threshold', 'created_at', 'is_viewed']
    list_filter = ['is_viewed', 'created_at']
    search_fields = ['product__title']
    readonly_fields = ['product', 'current_stock', 'threshold', 'created_at']

    def has_add_permission(self, request):
        return False


admin.site.register(LowStockAlert, LowStockAlertAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CartOrder, CartOrderAdmin)
admin.site.register(CartOrderProducts, CartOrderProductsAdmin)
admin.site.register(ProductReview, ProductReviewAdmin)
admin.site.register(wishlist_model, wishlistAdmin)
admin.site.register(Address, AddressAdmin)
admin.site.register(Coupon)

admin.site.register(ShippingAddress, ShippingAddressAdmin)

