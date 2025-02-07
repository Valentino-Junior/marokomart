from concurrent.futures import ThreadPoolExecutor
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
import logging

logger = logging.getLogger(__name__)

# Create a thread pool with max_workers
email_executor = ThreadPoolExecutor(max_workers=10)

class EmailSender:
    def __init__(self):
        self.executor = email_executor

    def send_email(self, subject, body, recipient_list, html_content=None):
        """Send email using thread pool executor"""
        try:
            # Print debug info
            print(f"Sending email to: {recipient_list}")
            print(f"Subject: {subject}")
            
            msg = EmailMultiAlternatives(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                recipient_list,
                alternatives=[(html_content, 'text/html')] if html_content else None
            )
            
            # Set email priority headers
            msg.extra_headers = {
                'X-Priority': '1',
                'X-MSMail-Priority': 'High',
                'Importance': 'High'
            }
            
            # Send immediately instead of using thread
            msg.send(fail_silently=False)
            return True
            
        except Exception as e:
            print(f"Email sending error: {str(e)}")
            logger.error(f"Failed to send email: {str(e)}")
            raise

def send_verification_email(user, verification_url, request):
    """Send verification email to user"""
    try:
        # Print debug info
        print(f"Preparing verification email for user: {user.email}")
        print(f"Verification URL: {verification_url}")
        
        context = {
            'user': user,
            'verification_url': verification_url,
            'domain': request.get_host(),
        }

        html_content = render_to_string(
            'userauths/emails/verification_email.html', 
            context
        )

        # Print template content for debugging
        print(f"Email HTML content: {html_content[:100]}...")

        email_sender = EmailSender()
        return email_sender.send_email(
            subject="Verify Your Email Address",
            body="Please verify your email address by clicking the link in this email.",
            recipient_list=[user.email],
            html_content=html_content
        )

    except Exception as e:
        print(f"Verification email error: {str(e)}")
        logger.error(f"Verification email error: {str(e)}")
        raise

def send_password_reset_email(user, reset_url, request):
    """Send password reset email to user"""
    try:
        print(f"Preparing password reset email for user: {user.email}")
        print(f"Reset URL: {reset_url}")
        
        context = {
            'user': user,
            'reset_url': reset_url,
            'domain': request.get_host(),
        }

        html_content = render_to_string(
            'userauths/emails/password_reset_email.html',
            context
        )

        print(f"Password reset email HTML content: {html_content[:100]}...")

        email_sender = EmailSender()
        return email_sender.send_email(
            subject="Password Reset Request",
            body="Please reset your password by clicking the link in this email.",
            recipient_list=[user.email],
            html_content=html_content
        )

    except Exception as e:
        print(f"Password reset email error: {str(e)}")
        logger.error(f"Password reset email error: {str(e)}")
        raise