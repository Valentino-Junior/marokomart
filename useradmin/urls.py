from django.urls import path
from useradmin import views

app_name = "useradmin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("products/", views.products, name="dashboard-products"),
    path("add-products/", views.add_product, name="dashboard-add-products"),
    
    path('edit-product/<str:pid>/', views.edit_product, name='dashboard-edit-products'), 
    path('delete-product-image/<str:pid>/<int:image_id>/', views.delete_product_image, name='delete_product_image'),


    path('contact_messages/', views.contact_messages, name='contact_messages'),
    path('contact-messages/count/', views.get_contact_message_count, name='get_contact_message_count'),


    path("delete-products/<pid>/", views.delete_product, name="dashboard-delete-products"),


    path("orders/", views.orders, name="orders"),
    path("order_detail/<id>/", views.order_detail, name="order_detail"),
    path("orders/count/", views.get_orders_count, name="get_orders_count"),


    path("change_order_status/<oid>/", views.change_order_status, name="change_order_status"),
    path("shop_page/", views.shop_page, name="shop_page"),
    path("settings/", views.settings, name="settings"),
    path("change_password/", views.change_password, name="change_password"),


    path('product_reviews/', views.product_reviews, name='product_reviews'),
    path('product_reviews/count/', views.get_product_review_count, name='get_product_review_count'),


    path('support-tickets/', views.support_tickets, name='support_tickets'),
    path('support-ticket/<int:ticket_id>/', views.get_ticket_details, name='get_ticket_details'),
    path('support-ticket/<int:ticket_id>/respond/', views.respond_to_ticket, name='respond_to_ticket'),
    path('unread-tickets-count/', views.get_unread_tickets_count, name='unread_tickets_count'),


    path('order_reviews/', views.order_reviews, name='order_reviews'),
    path('order_review/<int:review_id>/', views.get_order_review_details, name='get_order_review_details'),
    path('unread-order_reviews-count/', views.get_unread_order_reviews_count, name='get_unread_order_reviews_count'),


    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/create/', views.coupon_create, name='coupon_create'),
    path('coupons/<int:pk>/update/', views.coupon_update, name='coupon_update'),
    path('coupons/<int:pk>/delete/', views.coupon_delete, name='coupon_delete'),

    path('update-payment-status/<str:oid>/', views.update_payment_status, name='update_payment_status'),
]
