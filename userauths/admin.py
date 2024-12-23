from django.contrib import admin
from userauths.models import User, ContactUs, Profile

class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'bio', 'date_of_birth', 'is_email_verified']

class ContactUsAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'subject', 'message', 'is_viewed', 'created_at',]


# class ProfileAdmin(admin.ModelAdmin):
#     list_display = ['user', 'full_name', 'bio', 'phone']


admin.site.register(User, UserAdmin)
admin.site.register(ContactUs, ContactUsAdmin)
admin.site.register(Profile)