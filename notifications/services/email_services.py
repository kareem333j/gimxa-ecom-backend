from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
    
def send_html_email(subject, to_email, context, email_type="default_notification"):
    template_map = {
        "default_notification": "emails/default/notification.html",
        "code_sent": "emails/code.html",
        "payment_success": "emails/payments/success.html",
        "payment_failed": "emails/payments/failed.html",
        "credits_delivered": "emails/credits_delivered.html",
    }

    html_template = template_map.get(email_type, "emails/default/notification.html")
    context["domain"] = getattr(settings, "MAIN_DOMAIN", "")
    context["website_name"] = settings.WEBSITE_NAME
    context["website_url"] = settings.FRONTEND_URL
    context["BUSINESS_EMAIL"] = settings.BUSINESS_EMAIL
    context["HELP_CENTER_LINK"] = settings.HELP_CENTER_LINK
    context["COMPANY_ADDRESS"] = settings.COMPANY_ADDRESS
    context["FACEBOOK_LINK"] = settings.FACEBOOK_LINK
    context["INSTAGRAM_LINK"] = settings.INSTAGRAM_LINK
    context["TWITTER_LINK"] = settings.TWITTER_LINK
    context["YOUTUBE_LINK"] = settings.YOUTUBE_LINK
    # context["message"] = context["message"].replace("\n", "<br>")

    html_content = render_to_string(html_template, context)
    text_content = "Please check your email."

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()

def create_notification(serializer, user, subject, message):
    email_type = serializer.validated_data.get("email_type", "none")
    if email_type == 'none':
        pass
    elif email_type == "default":
        send_html_email(
            subject=subject or "New Notification",
            to_email=user.email,
            context={
                "user": user,
                "subject": subject or "New Notification",
                "date": timezone.now().strftime("%d %B, %Y"),
                "message": message or "You have a new notification",
            },
            email_type="default_notification",
        )
    elif email_type == "code_sent":
        code = serializer.initial_data.get("code")
        if not code:
            raise ValueError("Code is required for code_sent email type")
        send_html_email(
            subject=subject or "Your Credit Code",
            to_email=user.email,
            context={
                "user": user,
                "date": timezone.now().strftime("%d %B, %Y"),
                "message": message or "Your Code Is",
                "code": code,
            },
            email_type="code_sent",
        )
    elif email_type == "payment_success":
        send_html_email(
            subject=subject or "Payment Success",
            to_email=user.email,
            context={
                "user": user,
                "date": timezone.now().strftime("%d %B, %Y"),
                "message": message or "Your Payment Was Successful",
            },
            email_type="payment_success",
        )
    elif email_type == "payment_failed":
        send_html_email(
            subject=subject or "Payment Failed",
            to_email=user.email,
            context={
                "user": user,
                "date": timezone.now().strftime("%d %B, %Y"),
                "message": message or "Your Payment Failed",
            },
            email_type="payment_failed",
        )
    elif email_type == "credits_delivered":
        send_html_email(
            subject=subject or "Your Game Credits Are Now Available",
            to_email=user.email,
            context={
                "user": user,
                "date": timezone.now().strftime("%d %B, %Y"),
                "subject": subject or "Your Game Credits Are Now Available",
                "message": message or "Your Credits Have Been Delivered",
            },
            email_type="credits_delivered",
        )