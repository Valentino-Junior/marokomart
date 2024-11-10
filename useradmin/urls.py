from django.urls import path
from useradmin import views

app_name = "useradmin"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("products/", views.products, name="dashboard-products"),
    path("add-products/", views.add_product, name="dashboard-add-products"),
    
    path('edit-product/<str:pid>/', views.edit_product, name='dashboard-edit-products'), 
    path('delete-product-image/<str:pid>/<int:image_id>/', views.delete_product_image, name='delete_product_image'),

    path("delete-products/<pid>/", views.delete_product, name="dashboard-delete-products"),
    path("orders/", views.orders, name="orders"),
    path("order_detail/<id>/", views.order_detail, name="order_detail"),
    path("change_order_status/<oid>/", views.change_order_status, name="change_order_status"),
    path("shop_page/", views.shop_page, name="shop_page"),
    path("reviews/", views.reviews, name="reviews"),
    path("settings/", views.settings, name="settings"),
    path("change_password/", views.change_password, name="change_password"),


    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
]
