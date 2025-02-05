from django.contrib import admin
from .models import *
from core.models import *



@admin.register(Order_Review)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'order', 'comment', 'rating', 'is_viewed', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'order__oid')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    list_editable = ('is_viewed',)
    
    fieldsets = (
        ('Review Information', {
            'fields': ('user', 'order', 'rating')
        }),
        ('Review Content', {
            'fields': ('comment',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('user', 'order', 'issue_type', 'status','admin_response', 'is_viewed', 'created_at')
    list_filter = ('issue_type', 'status', 'created_at')
    search_fields = ('user__username', 'order__oid', 'message')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    
    list_editable = ('status', 'is_viewed', 'admin_response')  # Allow quick status updates from the list view
    
    fieldsets = (
        ('Ticket Information', {
            'fields': ('user', 'order', 'issue_type', 'status')
        }),
        ('Support Message', {
            'fields': ('message',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ('user', 'order', 'issue_type')
        return self.readonly_fields
    



class ProductImagesAdmin(admin.TabularInline):
    model = ProductImages

class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImagesAdmin]
    list_editable = ['title', 'price', 'product_status', 'low_stock_threshold']
    list_display = ['user', 'title', 'product_image', 'price', 'category', 'product_status', 'pid', 'stock_count', 'low_stock_threshold', 'is_special_offer', 'special_offer_price', 'special_offer_ends', 'is_new_arrival', 'new_arrival_ends']



class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'category_image']


class CartOrderAdmin(admin.ModelAdmin):
    list_editable = ['paid_status', 'product_status', 'sku', 'is_viewed']
    list_display = ['user', 'get_initial_price','discount_amount', 'price', 'get_applied_coupons',
                   'paid_status', 'payment_method', 'order_date', 'product_status', 
                   'external_reference', 'sku', 'is_viewed']
    list_filter = ['paid_status', 'product_status', 'payment_method', 'order_date']
    search_fields = ['user__username', 'external_reference', 'sku']
    readonly_fields = ['discount_amount', 'applied_coupons_data']

    def get_initial_price(self, obj):
        return obj.price + obj.discount_amount
    get_initial_price.short_description = 'Initial Price'

    def get_applied_coupons(self, obj):
        if obj.applied_coupons_data:
            return ', '.join([f"{coupon['code']} ({coupon['discount']}%)" 
                            for coupon in obj.applied_coupons_data])
        return '-'
    get_applied_coupons.short_description = 'Applied Coupons'


class CartOrderProductsAdmin(admin.ModelAdmin):
    list_display = ['order', 'invoice_no', 'item', 'image','qty', 'price', 'total']


class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'review', 'is_viewed', 'rating']


class wishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'date']




class ShippingAddressAdmin(admin.ModelAdmin):
    
    list_display = ['user', 'full_name', 'phone', 'email', 'region', 'shipping_instructions', 'is_default', 'date_added']



class LowStockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'current_stock', 'threshold', 'created_at', 'is_viewed']
    list_filter = ['is_viewed', 'created_at']
    search_fields = ['product__title']
    readonly_fields = ['product', 'current_stock', 'threshold', 'created_at']

    def has_add_permission(self, request):
        return False


@admin.register(PayHeroPayment)
class PayHeroPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'external_reference', 'payhero_reference', 'mpesa_receipt', 'amount', 'phone_number', 'shipping_address', 'status', 'created_at', 'updated_at')
    list_filter = ('status', 'created_at', 'updated_at')
    search_fields = ('user__username', 'phone_number', 'external_reference', 'mpesa_receipt')
    readonly_fields = ('created_at', 'updated_at')
    list_per_page = 20

    fieldsets = (
        (None, {
            'fields': ('user', 'amount', 'phone_number', 'checkout_request_id', 'mpesa_receipt', 'external_reference', 'status', 'cart_data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount', 'get_active_status', 'get_usage_stats', 
                   'get_expiry_status', 'get_shared_status', 'created_at']
    list_filter = ['active', 'shared_with_all', 'created_at']
    search_fields = ['code', 'email_subject']
    filter_horizontal = ['shared_with']
    readonly_fields = ['created_at', 'times_used', 'share_count', 'last_shared_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'discount', 'active', 'usage_limit', 'times_used')
        }),
        ('Validity', {
            'fields': ('created_at', 'expiry_date')
        }),
        ('Sharing Settings', {
            'fields': ('shared_with_all', 'shared_with', 'share_count', 'last_shared_at')
        }),
        ('Email Template', {
            'fields': ('email_subject', 'email_message'),
            'classes': ('collapse',)
        })
    )

    def get_active_status(self, obj):
        if obj.active:
            return '✔ Active'
        return '✘ Inactive'
    get_active_status.short_description = 'Status'

    def get_usage_stats(self, obj):
        return f'{obj.times_used} / {obj.usage_limit}'
    get_usage_stats.short_description = 'Usage'

    def get_expiry_status(self, obj):
        if not obj.expiry_date:
            return 'No Expiry'
        return str(obj.expiry_date)
    get_expiry_status.short_description = 'Expiry Status'

    def get_shared_status(self, obj):
        if obj.shared_with_all:
            return 'Shared with All'
        shared_count = obj.shared_with.count()
        if shared_count > 0:
            return f'Shared with {shared_count} users'
        return 'Not Shared'
    get_shared_status.short_description = 'Sharing Status'



@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['user', 'coupon', 'order', 'used_at']
    list_filter = ['used_at']
    search_fields = ['user__username', 'coupon__code']
    
  

    



admin.site.register(LowStockAlert, LowStockAlertAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(CartOrder, CartOrderAdmin)
admin.site.register(CartOrderProducts, CartOrderProductsAdmin)
admin.site.register(ProductReview, ProductReviewAdmin)
admin.site.register(wishlist_model, wishlistAdmin)

admin.site.register(ShippingAddress, ShippingAddressAdmin)

