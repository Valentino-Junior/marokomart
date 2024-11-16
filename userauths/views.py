from django.shortcuts import redirect, render
from userauths.forms import UserRegisterForm, ProfileForm
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.conf import settings
from userauths.models import Profile, User
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import EmailMultiAlternatives


from django.core.mail import send_mail, BadHeaderError
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes




# User = settings.AUTH_USER_MODEL

def register_view(request):
    
    if request.method == "POST":
        form = UserRegisterForm(request.POST or None)
        if form.is_valid():
            new_user = form.save()
            username = form.cleaned_data.get("username")
            messages.success(request, f"Hey {username}, You account was created successfully.")
            new_user = authenticate(username=form.cleaned_data['email'],
                                    password=form.cleaned_data['password1']
            )
            login(request, new_user)

            next_url = request.GET.get("next", 'core:index')
            return redirect(next_url)
    else:
        form = UserRegisterForm()


    context = {
        'form': form,
    }
    return render(request, "userauths/sign-up.html", context)


def login_view(request):
    if request.user.is_authenticated:
        messages.warning(request, f"Hey you are already Logged In.")
        return redirect("core:index")
    
    if request.method == "POST":
        email = request.POST.get("email") # peanuts@gmail.com
        password = request.POST.get("password") # getmepeanuts

        try:
            user = User.objects.get(email=email)
            user = authenticate(request, email=email, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, "You are logged in.")
                next_url = request.GET.get("next", 'core:index')
                return redirect(next_url)
            else:
                messages.warning(request, "User Does Not Exist, create an account.")
    
        except:
            messages.warning(request, f"User with {email} does not exist")
        

    
    return render(request, "userauths/sign-in.html")

        

def logout_view(request):

    logout(request)
    messages.success(request, "You logged out.")
    return redirect("userauths:sign-in")



def password_reset_request(request):
    if request.method == "POST" and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        email = request.POST.get("email", "").strip()
        
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Please enter your email address.'
            })
        
        try:
            user = User.objects.get(email=email)
            
            # Generate the reset token and URL
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            
            # Build the absolute URL for password reset
            domain = request.get_host()
            protocol = 'https' if request.is_secure() else 'http'
            reset_url = f"{protocol}://{domain}{reverse('userauths:password-reset-confirm', kwargs={'uidb64': uid, 'token': token})}"
            
            # Context for email template
            context = {
                "user": user,
                "reset_url": reset_url,
                "domain": domain,
            }
            
            # Render email content
            email_content = render_to_string(
                "userauths/emails/password_reset_email.html", 
                context
            )
            
            try:
                # Send email
                send_mail(
                    subject="Password Reset Request",
                    message="",  # Empty as we're sending HTML email
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=email_content,
                    fail_silently=False,
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Password reset instructions have been sent to your email.'
                })
                
            except Exception as e:
                print(f"Email sending failed: {str(e)}")  # For debugging
                return JsonResponse({
                    'success': False,
                    'message': 'Failed to send reset email. Please try again later.'
                })
                
        except User.DoesNotExist:
            # For security reasons, don't reveal if email exists or not
            return JsonResponse({
                'success': True,
                'message': 'If an account exists with this email, you will receive password reset instructions.'
            })
    
    return render(request, "userauths/password_reset.html")



def password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if request.method == "POST" and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if user is not None and default_token_generator.check_token(user, token):
            password1 = request.POST.get("password1")
            password2 = request.POST.get("password2")
            
            if not password1 or not password2:
                return JsonResponse({
                    'success': False,
                    'message': 'Please enter both passwords.'
                })
                
            if password1 != password2:
                return JsonResponse({
                    'success': False,
                    'message': 'Passwords do not match.'
                })
                
            if len(password1) < 8:
                return JsonResponse({
                    'success': False,
                    'message': 'Password must be at least 8 characters long.'
                })
                
            user.set_password(password1)
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Your password has been reset successfully.',
                'redirect_url': reverse('userauths:sign-in')
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Password reset link is invalid or has expired.'
            })
            
    if user is not None and default_token_generator.check_token(user, token):
        return render(request, "userauths/password_reset_confirm.html")
    else:
        return JsonResponse({
            'success': False,
            'message': 'Password reset link is invalid or has expired.'
        })
