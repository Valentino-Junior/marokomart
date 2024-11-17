from django.urls import path
from userauths import views

app_name = "userauths"

urlpatterns = [
    path("sign-up/", views.register_view, name="sign-up"),
    path("sign-in/", views.login_view, name="sign-in"),
    path("sign-out/", views.logout_view, name="sign-out"),
    path('change-password/', views.change_password, name='change-password'),
    
    path('password-reset/', views.password_reset_request, name='password-reset'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         views.password_reset_confirm, name='password-reset-confirm'),
]