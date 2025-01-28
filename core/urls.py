from django import views
from django.urls import path, include
from core.views import create_checkout_session, save_checkout_info, add_to_cart, add_to_wishlist, ajax_add_review, cart_view, category_list_view, category_product_list__view, checkout, customer_dashboard, delete_item_from_cart, filter_product, index, order_detail, product_detail_view, product_list_view, remove_wishlist, search_view, update_cart, wishlist_view, contact, about_us, purchase_guide, privacy_policy, order_tracking_view, new_arrivals_view, special_offers_view, apply_coupon_view, get_shipping_addresses,save_shipping_address, clear_cart, track_order_ajax, my_orders_view, cancel_order, delete_address, make_address_default, redirect_to_checkout, contact_submit, submit_review, submit_support_ticket, get_support_tickets, edit_shipping_address, refund_policy, terms_conditions,mpesa_callback, mpesa_test, mpesa_payment, cash_payment

app_name = "core"

urlpatterns = [

    # Homepage
    path("", index, name="index"),
    path("products/", product_list_view, name="product-list"),
    path("product/<pid>/", product_detail_view, name="product-detail"),
    path("category/", category_list_view, name="category-list"),
    path("category/<cid>/", category_product_list__view, name="category-product-list"),
    path("ajax-add-review/<int:pid>/", ajax_add_review, name="ajax-add-review"),
    path("search/", search_view, name="search"),
    path("filter-products/", filter_product, name="filter-product"),
    path("add-to-cart/", add_to_cart, name="add-to-cart"),
    path("cart/", cart_view, name="cart"),
    path("delete-from-cart/", delete_item_from_cart, name="delete-from-cart"),
    path("update-cart/", update_cart, name="update-cart"),
    path("api/create_checkout_session/<oid>/", create_checkout_session, name="api_checkout_session"),
    path("save_checkout_info/", save_checkout_info, name="save_checkout_info"),
    path("checkout/<str:oid>/", checkout, name="checkout"),
    path("clear_cart/", clear_cart, name="clear_cart"),

    path("redirect-to-checkout/", redirect_to_checkout, name="redirect_to_checkout"),
    path('edit-shipping-address/<int:address_id>/', edit_shipping_address, name='edit_shipping_address'),
   


    path('paypal/', include('paypal.standard.ipn.urls')),
    # path("payment-completed/<oid>/", payment_completed_view, name="payment-completed"),
    # path("payment-failed/", payment_failed_view, name="payment-failed"),
    path("dashboard/", customer_dashboard, name="dashboard"),
    path("dashboard/order/<int:id>", order_detail, name="order-detail"),
    path("wishlist/", wishlist_view, name="wishlist"),
    path("add-to-wishlist/", add_to_wishlist, name="add-to-wishlist"),
    path("remove-from-wishlist/", remove_wishlist, name="remove-from-wishlist"),
    path("contact/", contact, name="contact"),
    path("contact/submit/", contact_submit, name="contact_submit"),
    path("about_us/", about_us, name="about_us"),
    path("purchase_guide/", purchase_guide, name="purchase_guide"),


    
   
    path('privacy-policy/', privacy_policy, name='privacy-policy'),
    path('refund-policy/', refund_policy, name='refund-policy'),
    path('terms-and-conditions/', terms_conditions, name='terms-conditions'),


    path("order_tracking/", order_tracking_view, name="order_tracking"),
    path('track-order-ajax/', track_order_ajax, name='track_order_ajax'),
    path('my-orders/', my_orders_view, name='my_orders'),
    path('api/orders/<str:order_id>/cancel/', cancel_order, name='cancel_order'),
   

    path('submit-review/', submit_review, name='submit_review'),
    path('api/support/submit/', submit_support_ticket, name='submit_support_ticket'),
    path('get-support-tickets/<str:order_id>/', get_support_tickets, name='get_support_tickets'),


    path("special_offers/", special_offers_view, name="special_offers"),
    path("new_arrivals/", new_arrivals_view, name="new_arrivals"),
    path('apply-coupon/', apply_coupon_view, name='apply-coupon'),

    path('get-shipping-addresses/', get_shipping_addresses, name='get_shipping_addresses'),
    path('save-shipping-address/', save_shipping_address, name='save_shipping_address'),
    path('save-checkout-info/', save_checkout_info, name='save_checkout_info'),


    path('make-address-default/<int:address_id>/', make_address_default, name='make-address-default'),
    path('delete-address/<int:address_id>/', delete_address, name='delete-address'),

   

    path('mpesa/callback/', mpesa_callback, name='mpesa_callback'),
    path('mpesa/payment/', mpesa_payment, name='mpesa_payment'),
    path('cash/payment/', cash_payment, name='cash_payment'),

    path('mpesa-test/', mpesa_test, name='mpesa_test'),


]