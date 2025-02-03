# utils/email_thread.py
import threading
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags
from django.conf import settings

class EmailThread(threading.Thread):
    def __init__(self, subject, html_message, recipient_list):
        self.subject = subject
        self.recipient_list = recipient_list
        self.html_message = html_message
        self.text_message = strip_tags(html_message)
        threading.Thread.__init__(self)

    def run(self):
        try:
            msg = EmailMultiAlternatives(
                subject=self.subject,
                body=self.text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=self.recipient_list
            )
            msg.attach_alternative(self.html_message, "text/html")
            msg.send(fail_silently=False)
        except Exception as e:
            print(f"Failed to send email: {str(e)}")

def send_email_threaded(subject, html_message, recipient_list):
    EmailThread(subject, html_message, recipient_list).start()