from enum import unique
from django.db import models
from django.contrib.auth.models import AbstractUser 
from django.db.models.signals import post_save
from django.utils import timezone


class User(AbstractUser):
    USER_TYPE_CHOICES = [
        ('CLIENT', 'Client'),
        ('VENDOR', 'Vendor'),
        ('STAFF', 'Staff'),
        ('ADMIN', 'Admin'),
    ]
    
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100)
    bio = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True)
    is_email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    user_type = models.CharField(
        max_length=10, 
        choices=USER_TYPE_CHOICES,
        default='CLIENT'
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.username


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to="image", null=True, blank=True)
    full_name = models.CharField(max_length=200, null=True, blank=True)
    bio = models.CharField(max_length=200, null=True, blank=True)
    phone = models.CharField(max_length=200, null=True, blank=True) 
    address = models.CharField(max_length=200, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    
    
    def __str__(self):
        return f"{self.full_name} - {self.bio}"


class ContactUs(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.CharField(max_length=200)
    phone = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=200) 
    message = models.TextField()
    is_viewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_unread_count(cls):
        return cls.objects.filter(is_viewed=False).count()

    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} - {self.subject}"
    

    
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

 
post_save.connect(create_user_profile, sender=User)
post_save.connect(save_user_profile, sender=User)    



