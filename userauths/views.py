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
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.utils.crypto import get_random_string



# User = settings.AUTH_USER_MODEL

def register_view(request):
    if request.method == "POST":
        form = UserRegisterForm(request.POST or None)
        if form.is_valid():
            # Create user but don't save yet
            new_user = form.save(commit=False)
            new_user.is_active = False  # Deactivate account until verification
            new_user.email_verification_token = get_random_string(64)
            new_user.save()

            # Generate verification URL
            verification_url = request.build_absolute_uri(
                reverse('userauths:verify-email', kwargs={
                    'user_id': new_user.id,
                    'token': new_user.email_verification_token
                })
            )

            # Prepare email content
            context = {
                'user': new_user,
                'verification_url': verification_url,
                'domain': request.get_host(),
            }

            # Render email template
            email_html_content = render_to_string(
                'userauths/emails/verification_email.html', 
                context
            )

            # Send verification email
            try:
                msg = EmailMultiAlternatives(
                    subject="Verify Your Email Address",
                    body="Please verify your email address by clicking the link in this email.",  # Basic fallback text
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[new_user.email]
                )
                msg.attach_alternative(email_html_content, "text/html")
                msg.send()

                messages.success(
                    request, 
                    f"Hi {new_user.username}, please check your email to verify your account."
                )
                return redirect('userauths:verification-sent')
            except Exception as e:
                print(f"Email sending error: {str(e)}")  # For debugging
                new_user.delete()  # Delete user if email sending fails
                messages.error(
                    request, 
                    "Registration failed. Please try again later."
                )
                return redirect('userauths:sign-up')
    else:
        form = UserRegisterForm()

    context = {
        'form': form,
    }
    return render(request, "userauths/sign-up.html", context)



def verify_email(request, user_id, token):
    try:
        user = User.objects.get(id=user_id, email_verification_token=token)
        if not user.is_email_verified:
            user.is_email_verified = True
            user.is_active = True
            user.email_verification_token = None  # Clear the token
            user.save()
            messages.success(request, "Your email has been verified. You can now login.")
        else:
            messages.info(request, "Your email was already verified.")
        return redirect('userauths:sign-in')
    except User.DoesNotExist:
        messages.error(request, "Invalid verification link.")
        return redirect('userauths:sign-up')
    


def verification_sent(request):
    return render(request, 'userauths/verification_sent.html')



def login_view(request):
    if request.user.is_authenticated:
        messages.warning(request, f"Hey you are already logged in.")
        return redirect("core:index")
    
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            # First check if user exists
            user = User.objects.get(email=email)
            
            # Then attempt authentication
            authenticated_user = authenticate(request, email=email, password=password)

            if authenticated_user is not None:
                # Check if email is verified
                if authenticated_user.is_email_verified:
                    login(request, authenticated_user)
                    messages.success(request, "You are logged in.")
                    next_url = request.GET.get("next", 'core:index')
                    return redirect(next_url)
                else:
                    messages.warning(
                        request, 
                        "Please verify your email first. Check your inbox for the verification link."
                    )
            else:
                messages.error(request, "Invalid password. Please try again.")
        
        except User.DoesNotExist:
            messages.warning(
                request, 
                "No account found with this email. Please create an account."
            )
        except Exception as e:
            messages.error(request, "An error occurred. Please try again.")
            print(f"Login error: {str(e)}")  # For debugging
    
    return render(request, "userauths/sign-in.html")


@login_required
@require_http_methods(["POST"])
def change_password(request):
    try:
        # Get form data
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Validate input
        if not all([current_password, new_password, confirm_password]):
            return JsonResponse({
                'success': False,
                'message': 'All fields are required.'
            })

        # Check if current password is correct
        if not request.user.check_password(current_password):
            return JsonResponse({
                'success': False,
                'message': 'Current password is incorrect.'
            })

        # Check if new passwords match
        if new_password != confirm_password:
            return JsonResponse({
                'success': False,
                'message': 'New passwords do not match.'
            })

        # Validate password strength
        if len(new_password) < 8:
            return JsonResponse({
                'success': False,
                'message': 'Password must be at least 8 characters long.'
            })

        # Set new password
        request.user.set_password(new_password)
        request.user.save()

        # Keep user logged in
        update_session_auth_hash(request, request.user)

        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully!'
        })

    except Exception as e:
        print(f"Password change error: {str(e)}")  # For debugging
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        })
        

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
