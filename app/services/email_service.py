"""Minimal EmailService for sending transactional emails.

Focuses only on delivery and template rendering. Token logic is handled
by VerificationService.
"""

from __future__ import annotations

import logging
from typing import Optional, List

from flask import current_app, render_template, url_for

logger = logging.getLogger(__name__)


def _external_url(endpoint: str, **values) -> str:
    """Build an absolute URL for an email link.

    SECURITY: when ``APP_BASE_URL`` is configured we prefix the path-only URL
    with that trusted base and ignore the request Host header entirely. Without
    it (e.g. local dev) we fall back to Flask's Host-based ``_external`` URL.
    The Host-based path is vulnerable to host-header injection — a spoofed
    Host/X-Forwarded-Host would otherwise place a valid reset token on an
    attacker-controlled domain — so production MUST set APP_BASE_URL.
    """
    base = (current_app.config.get("APP_BASE_URL") or "").rstrip("/")
    if base:
        path = url_for(endpoint, _external=False, **values)
        return f"{base}{path}"
    return url_for(endpoint, _external=True, **values)


class EmailService:
    mail = None
    app = None

    @staticmethod
    def init_mail(app):
        """Initialize Flask-Mail and store app reference."""
        try:
            from flask_mail import Mail
            EmailService.mail = Mail(app)
            EmailService.app = app
            logger.debug("EmailService: Flask-Mail initialized")
        except Exception as e:
            EmailService.mail = None
            EmailService.app = app
            logger.debug(f"EmailService: Flask-Mail not available: {e}")

    @staticmethod
    def send_email(
        subject: str, 
        recipients: List[str], 
        html_body: str = "", 
        text_body: str = ""
    ) -> bool:
        """Send email via Flask-Mail with SMTP fallback."""
        if not EmailService.mail:
            return EmailService._send_via_smtplib(subject, recipients, html_body, text_body)

        try:
            from flask_mail import Message
            sender = current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@localhost")
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=text_body,
                html=html_body,
                sender=sender,
            )
            EmailService.mail.send(msg)
            return True
        except Exception:
            logger.exception("Flask-Mail send failed, trying smtplib fallback")
            return EmailService._send_via_smtplib(subject, recipients, html_body, text_body)

    @staticmethod
    def _send_via_smtplib(
        subject: str, 
        recipients: List[str], 
        html_body: str = "", 
        text_body: str = ""
    ) -> bool:
        """Fallback sender using standard smtplib."""
        import smtplib
        from email.message import EmailMessage

        app = EmailService.app or current_app
        try:
            server = app.config.get("MAIL_SERVER", "smtp.gmail.com")
            port = int(app.config.get("MAIL_PORT", 587))
            use_tls = bool(app.config.get("MAIL_USE_TLS", True))
            use_ssl = bool(app.config.get("MAIL_USE_SSL", False))
            username = app.config.get("MAIL_USERNAME")
            password = app.config.get("MAIL_PASSWORD")
            sender = app.config.get("MAIL_DEFAULT_SENDER", username or "noreply@localhost")

            if not username or not password:
                logger.warning("SMTP credentials missing for fallback")
                return False

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            msg.set_content(text_body or "")
            if html_body:
                msg.add_alternative(html_body, subtype="html")

            if use_ssl:
                smtp = smtplib.SMTP_SSL(server, port, timeout=10)
            else:
                smtp = smtplib.SMTP(server, port, timeout=10)

            try:
                smtp.ehlo()
                if use_tls and not use_ssl:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(msg)
                return True
            finally:
                smtp.quit()
        except Exception:
            logger.exception("SMTP fallback failed")
            return False

    def send_verification_email(self, user, token: str, purpose: Optional[str] = None) -> bool:
        """Render and send a verification email based on purpose."""
        # 1. Determine URL and Subject
        if purpose == "admin_reset":
            subject = "Admin password reset for your account"
            verification_url = _external_url("auth.reset_complete_page", username=user.username, reset_token=token)
        elif purpose == "user_reset":
            subject = "Reset Password for Your Account"
            verification_url = _external_url("auth.reset_verify_code_page", username=user.username)
        else:
            subject = "Verify your account"
            verification_url = _external_url("auth.verify_page", username=user.username)

        # 2. Render HTML body from template
        try:
            html_body = render_template(
                "emails/verify_email.html",
                username=user.username,
                token=token,
                verification_url=verification_url,
                purpose=purpose,
                subject=subject
            )
        except Exception:
            logger.exception("Failed to render email template")
            return False

        # 3. Simple text fallback
        text_body = f"Hello {user.username},\n\nYour code is: {token}\n\nLink: {verification_url}"

        return self.send_email(subject, [user.email], html_body=html_body, text_body=text_body)


email_service = EmailService()
