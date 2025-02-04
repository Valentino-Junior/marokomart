from django import forms
from django.contrib.auth.forms import UserCreationForm
from userauths.models import User, Profile
from django.core.exceptions import ValidationError
from datetime import date


class UserRegisterForm(UserCreationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Username"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder":"Email"}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder":"Password"}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder":"Confirm Password"}))
    date_of_birth = forms.DateField(
        widget=forms.DateInput(attrs={
            "placeholder":"Date of Birth",
            "type": "date",
            "class": "form-control"
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'date_of_birth',]
        

    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        if age < 18:
            raise ValidationError('You must be at least 18 years old to register.')
        
        return dob

    def save(self, commit=True):
       user = super().save(commit=False)
       user.user_type = 'CLIENT'
       if commit:
           user.save()
       return user


# Will add this in future to signup with different user types
# class UserRegisterForm(UserCreationForm):
#     # Existing fields...
#     user_type = forms.ChoiceField(
#         choices=User.USER_TYPE_CHOICES,
#         widget=forms.Select(attrs={
#             "class": "form-control",
#             "placeholder": "Account Type"
#         })
#     )

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'date_of_birth', 'user_type']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Optionally restrict available choices
#         allowed_types = ['CLIENT', 'VENDOR']  # Example: only allow client/vendor signup
#         self.fields['user_type'].choices = [
#             (choice[0], choice[1]) for choice in User.USER_TYPE_CHOICES 
#             if choice[0] in allowed_types
#         ]

class ProfileForm(forms.ModelForm):
    full_name = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Full Name"}))
    bio = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Bio"}))
    phone = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Phone"}))
    address = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Address"}))
    country = forms.CharField(widget=forms.TextInput(attrs={"placeholder":"Country"}))


    class Meta:
        model = Profile
        fields = ['full_name', 'image', 'bio', 'phone', 'address', 'country']