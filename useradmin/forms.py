# forms.py
from django import forms
from core.models import Product, ProductImages, Category, Coupon


class CategoryForm(forms.ModelForm):
    title = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Category Title'
        })
    )
    image = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        required=False
    )

    class Meta:
        model = Category
        fields = ['title', 'image']


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['discount', 'active', 'expiry_date', 'usage_limit']
        widgets = {
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Discount percentage (1-100)',
                'min': '1',
                'max': '100'
            }),
            'active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'expiry_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'usage_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of times this coupon can be used',
                'min': '1'
            })
        }



class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class EditProductForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'placeholder': "Product Title", "class":"form-control"}))
    description = forms.CharField(widget=forms.Textarea(attrs={'placeholder': "Product Description", "class":"form-control"}))
    price = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "Sale Price", "class":"form-control"}))
    old_price = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "Old Price", "class":"form-control"}))
    stock_count = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "How many are in stock?", "class":"form-control"}))
    low_stock_threshold = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "What is your low stock threshold?", "class":"form-control"}))
    image = forms.ImageField(widget=forms.FileInput(attrs={"class":"form-control"}), required=False)
    additional_images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )
    
    # Special Offer Fields
    is_special_offer = forms.BooleanField(required=False)
    special_offer_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Special Offer Price'
        })
    )
    special_offer_ends = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )

    # New Arrival Fields
    is_new_arrival = forms.BooleanField(required=False)
    new_arrival_ends = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    stock_status = forms.ChoiceField(
        required=False,
        choices=[
            ('in_stock', 'In Stock'),
            ('new_stock', 'New Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Product
        fields = [
            'title',
            'image',
            'description',
            'price',
            'old_price',
            'stock_count',
            'low_stock_threshold',
            'category',
            'is_special_offer',
            'special_offer_price',
            'special_offer_ends',
            'is_new_arrival',
            'new_arrival_ends',
            'stock_status',
        ]

class AddProductForm(forms.ModelForm):
    title = forms.CharField(widget=forms.TextInput(attrs={'placeholder': "Product Title", "class":"form-control"}))
    description = forms.CharField(widget=forms.Textarea(attrs={'placeholder': "Product Description", "class":"form-control"}))
    price = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "Sale Price", "class":"form-control"}))
    old_price = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "Old Price", "class":"form-control"}))
    stock_count = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "How many are in stock?", "class":"form-control"}))
    low_stock_threshold = forms.CharField(widget=forms.NumberInput(attrs={'placeholder': "What is your low stock threshold?", "class":"form-control"}))
    image = forms.ImageField(widget=forms.FileInput(attrs={"class":"form-control"}))
    additional_images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )

    # Special Offer Fields
    is_special_offer = forms.BooleanField(required=False)
    special_offer_price = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Special Offer Price'
        })
    )
    special_offer_ends = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )

    # New Arrival Fields
    is_new_arrival = forms.BooleanField(required=False)
    new_arrival_ends = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    stock_status = forms.ChoiceField(
        required=False,
        choices=[
            ('in_stock', 'In Stock'),
            ('new_stock', 'New Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Product
        fields = [
            'title',
            'image',
            'description',
            'price',
            'old_price',
            'stock_count',
            'low_stock_threshold',
            'category',
            'is_special_offer',
            'special_offer_price',
            'special_offer_ends',
            'is_new_arrival',
            'new_arrival_ends',
            'stock_status',
        ]