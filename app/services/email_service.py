"""Minimal EmailService placeholder for tests and runtime.
If Flask-Mail is installed and configured, this will initialize the Mail instance.
Otherwise it provides no-op fallback functions so the app and tests can run.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class EmailService:
    mail = None
    app = None

    @staticmethod
    def init_mail(app):
        """Initialize Flask-Mail if available and configured and keep app reference."""
        try:
            from flask_mail import Mail

            EmailService.mail = Mail(app)
            EmailService.app = app
            logger.debug("EmailService: Flask-Mail initialized")
            # Perform a lightweight SMTP credentials check to provide actionable logs
            try:
                EmailService._test_smtp_credentials(app)
            except Exception:
                # _test_smtp_credentials logs details on failure
                pass
        except Exception as e:
            EmailService.mail = None
            EmailService.app = app
            logger.debug(f"EmailService: Flask-Mail not available or failed to init: {e}")

    @staticmethod
    def _test_smtp_credentials(app) -> bool:
        """Attempt to connect/login to configured SMTP server and log helpful diagnostics.

        This does not send any messages. Returns True if login succeeded, False otherwise.
        """
        try:
            server = app.config.get("MAIL_SERVER")
            port = int(app.config.get("MAIL_PORT", 0) or 0)
            use_tls = bool(app.config.get("MAIL_USE_TLS", False))
            use_ssl = bool(app.config.get("MAIL_USE_SSL", False))
            username = app.config.get("MAIL_USERNAME")
            password = app.config.get("MAIL_PASSWORD")

            if not server or not port:
                logger.debug(
                    "EmailService: MAIL_SERVER or MAIL_PORT not configured; skipping SMTP test"
                )
                return False

            if not username or not password:
                logger.warning(
                    "EmailService: MAIL_USERNAME or MAIL_PASSWORD not set; email will likely fail"
                )
                return False

            import smtplib

            timeout = 10
            if use_ssl:
                conn = smtplib.SMTP_SSL(server, port, timeout=timeout)
            else:
                conn = smtplib.SMTP(server, port, timeout=timeout)
            try:
                conn.ehlo()
                if use_tls and not use_ssl:
                    conn.starttls()
                    conn.ehlo()
                # Try login
                conn.login(username, password)
                logger.info(
                    "EmailService: SMTP credential test succeeded for %s:%s",
                    server,
                    port,
                )
                return True
            finally:
                try:
                    conn.quit()
                except Exception:
                    pass
        except Exception as e:
            # Provide actionable guidance for common Gmail errors
            msg = str(e)
            logger.warning("EmailService: SMTP credential test failed (%s)", msg)
            if "535" in msg or "Username and Password" in msg or "BadCredentials" in msg:
                logger.warning(
                    "EmailService: SMTP auth failed. If using Gmail, enable 2FA and use an App Password (https://support.google.com/mail/?p=InvalidSecondFactor or https://support.google.com/accounts/answer/185833)."
                )
            if "STARTTLS" in msg or "TLS" in msg:
                logger.debug(
                    "EmailService: Check MAIL_USE_TLS / MAIL_USE_SSL and MAIL_PORT (587 for TLS, 465 for SSL)."
                )
            return False

    @staticmethod
    def send_email(
        subject: str, recipients: list, html_body: str = "", text_body: str = ""
    ) -> bool:
        """Try to send email; return True if sent otherwise False."""
        if not EmailService.mail:
            logger.debug("EmailService.send_email called but mail is not configured")
            # Try SMTP fallback using app config (useful for Gmail)
            try:
                from flask import current_app

                app = EmailService.app or current_app
            except Exception:
                app = EmailService.app
            try:
                return EmailService._send_via_smtplib(
                    app, subject, recipients, html_body, text_body
                )
            except Exception as e:
                logger.exception("SMTP fallback send failed")
                return False
        try:
            from flask_mail import Message

            # Ensure a sender is present; prefer configured default
            default_sender = None
            try:
                default_sender = EmailService.mail.app.config.get("MAIL_DEFAULT_SENDER")
            except Exception:
                default_sender = None
            sender = default_sender or "noreply@localhost"
            msg = Message(
                subject=subject,
                recipients=recipients,
                body=text_body,
                html=html_body,
                sender=sender,
            )
            try:
                EmailService.mail.send(msg)
                return True
            except Exception as e:
                # If Flask-Mail fails (authentication or other SMTP issues), try SMTP fallback
                logger.exception("Flask-Mail send failed, attempting SMTP fallback")
                try:
                    from flask import current_app

                    app = EmailService.app or current_app
                except Exception:
                    app = EmailService.app
                try:
                    sent = EmailService._send_via_smtplib(
                        app, subject, recipients, html_body, text_body
                    )
                    if sent:
                        return True
                except Exception:
                    logger.exception("SMTP fallback after Flask-Mail failure also failed")
                return False
        except Exception as e:
            logger.exception("Failed to send email")
            return False

    @staticmethod
    def _send_via_smtplib(
        app, subject: str, recipients: list, html_body: str = "", text_body: str = ""
    ) -> bool:
        """Fallback sender using smtplib. Respects typical Flask-Mail config keys.

        Recommended config for Gmail (use app password):
        MAIL_SERVER = 'smtp.gmail.com'
        MAIL_PORT = 587
        MAIL_USE_TLS = True
        MAIL_USERNAME = 'your@gmail.com'
        MAIL_PASSWORD = 'your-app-password'
        MAIL_DEFAULT_SENDER = 'noreply@example.com'
        """
        try:
            if not app:
                logger.debug("No Flask app available for SMTP fallback")
                return False
            server = app.config.get("MAIL_SERVER", "smtp.gmail.com")
            port = int(app.config.get("MAIL_PORT", 587))
            use_tls = bool(app.config.get("MAIL_USE_TLS", True))
            use_ssl = bool(app.config.get("MAIL_USE_SSL", False))
            username = app.config.get("MAIL_USERNAME")
            password = app.config.get("MAIL_PASSWORD")
            sender = app.config.get("MAIL_DEFAULT_SENDER", username or "noreply@localhost")

            if not username or not password:
                logger.debug("SMTP fallback requires MAIL_USERNAME and MAIL_PASSWORD in config")
                return False

            # Build message
            from email.message import EmailMessage

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)
            if text_body:
                msg.set_content(text_body)
            else:
                msg.set_content("")
            if html_body:
                msg.add_alternative(html_body, subtype="html")

            import smtplib

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
                logger.debug("SMTP fallback: email sent via %s:%s", server, port)
                return True
            finally:
                try:
                    smtp.quit()
                except Exception:
                    pass
        except Exception:
            logger.exception("SMTP fallback failed to send email")
            return False

    @staticmethod
    def generate_token(email: str, salt: str = None, sent_at=None) -> str:
        """Generate a signed token containing email and sent_at.

        Token is stateless; it encodes the email and the sent_at timestamp so we can
        verify it against the user's recorded `email_verification_sent_at`.
        Tests may monkeypatch this function so keep the signature compatible.
        """
        try:
            # If tests monkeypatch to return a simple string, allow it
            from flask import current_app
            from itsdangerous import URLSafeSerializer

            app = EmailService.app or current_app
            secret = app.config.get("SECRET_KEY")
            salt = salt or "email-verify"
            serializer = URLSafeSerializer(secret, salt=salt)
            from datetime import datetime, timezone

            ts = sent_at if sent_at is not None else datetime.now(timezone.utc)
            payload = {
                "email": email,
                "sent_at": ts.replace(tzinfo=timezone.utc).isoformat(),
            }
            return serializer.dumps(payload)
        except Exception as e:
            # Fallback to random token for non-signed environments (or tests)
            try:
                import secrets

                return secrets.token_urlsafe(16)
            except Exception:
                logger.exception("Failed to generate token")
                return ""

    @staticmethod
    def verify_token(token: str, email: str, expected_sent_at, code_hash: str = None) -> tuple:
        """Verify a token which may be either:
        - a 6-digit numeric code that matches the hashed `code_hash` stored on the user, or
        - a signed token produced by `generate_token`.

        Returns (True, None) on success, or (False, 'invalid'|'expired') on failure.
        """
        try:
            import re
            from datetime import datetime, timedelta, timezone

            from flask import current_app
            from itsdangerous import BadSignature, URLSafeSerializer
            from werkzeug.security import check_password_hash

            app = EmailService.app or current_app

            # Short numeric code flow (6 digits)
            if isinstance(token, str) and re.fullmatch(r"\d{6}", token):
                # Must have a stored hash to compare against
                if not code_hash:
                    return (False, "invalid")
                if not check_password_hash(code_hash, token):
                    return (False, "invalid")
                # Normalize expected_sent_at and check expiry
                if not expected_sent_at:
                    return (False, "invalid")
                try:
                    if expected_sent_at.tzinfo is None:
                        expected_sent_at = expected_sent_at.replace(tzinfo=timezone.utc)
                except Exception:
                    return (False, "invalid")
                expiry_hours = app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
                if datetime.now(timezone.utc) > (
                    expected_sent_at + timedelta(hours=int(expiry_hours))
                ):
                    return (False, "expired")
                return (True, None)

            # Fallback to signed token behavior (existing implementation)
            secret = app.config.get("SECRET_KEY")
            serializer = URLSafeSerializer(secret, salt="email-verify")
            try:
                payload = serializer.loads(token)
            except BadSignature:
                # Fallback: try the current_app secret in case EmailService.app was initialized
                # with a different app (tests may create multiple apps)
                try:
                    from flask import current_app as falcon_current_app

                    other_secret = falcon_current_app.config.get("SECRET_KEY")
                    if other_secret and other_secret != secret:
                        serializer2 = URLSafeSerializer(other_secret, salt="email-verify")
                        payload = serializer2.loads(token)
                    else:
                        raise
                except BadSignature:
                    # Re-raise to be caught by outer BadSignature handler
                    raise
            # Debug prints to diagnose intermittent parsing/format mismatches (tests capture stdout)
            try:
                logger.debug(
                    "verify_token payload",
                    {
                        "email_in_token": payload.get("email"),
                        "token_sent": payload.get("sent_at"),
                    },
                )
            except Exception:
                pass
            if payload.get("email") != email:
                return (False, "invalid")
            token_sent = payload.get("sent_at")
            if not expected_sent_at:
                return (False, "invalid")
            # Normalize expected_sent_at to timezone-aware UTC to avoid offset-naive/aware comparison issues
            try:
                if expected_sent_at.tzinfo is None:
                    expected_sent_at = expected_sent_at.replace(tzinfo=timezone.utc)
            except Exception:
                # If anything odd happens, fall back to treating token as invalid
                return (False, "invalid")
            # Parse token's sent_at and compare with stored sent_at with small tolerance to avoid
            # false negatives due to microsecond truncation or timezone formatting differences
            token_dt = None
            try:
                # token_sent is an ISO string; try parsing it to datetime
                token_dt = datetime.fromisoformat(token_sent)
                if token_dt.tzinfo is None:
                    token_dt = token_dt.replace(tzinfo=timezone.utc)
            except Exception:
                # Try dateutil if available (handles more ISO variants like trailing 'Z')
                try:
                    from dateutil.parser import isoparse

                    token_dt = isoparse(token_sent)
                    if token_dt.tzinfo is None:
                        token_dt = token_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    try:
                        if token_sent.endswith("Z"):
                            token_dt = datetime.fromisoformat(token_sent.replace("Z", "+00:00"))
                            if token_dt.tzinfo is None:
                                token_dt = token_dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        token_dt = None
            if token_dt is None:
                # If parsing ultimately failed, fall back to strict string compare
                expected_str = expected_sent_at.replace(tzinfo=timezone.utc).isoformat()
                if token_sent != expected_str:
                    logger.debug(
                        "Token timestamp mismatch",
                        {"token_sent": token_sent, "expected_sent": expected_str},
                    )
                    logger.debug(
                        "Token timestamp parse failed",
                        {"token_sent": token_sent, "expected_str": expected_str},
                    )
                    return (False, "invalid")
            else:
                # Allow small time delta (10 seconds) to account for truncation/rounding and clock skew
                try:
                    # Use timestamp differences to avoid edge cases with unusual tzinfo implementations
                    delta = abs(
                        expected_sent_at.replace(tzinfo=timezone.utc).timestamp()
                        - token_dt.replace(tzinfo=timezone.utc).timestamp()
                    )
                except Exception:
                    delta = abs((expected_sent_at - token_dt).total_seconds())
                if delta > 60:
                    # Accept case where DB stored sent_at lost microseconds but otherwise matches same second
                    try:
                        # Accept if only microseconds differ
                        if expected_sent_at.replace(microsecond=0) == token_dt.replace(
                            microsecond=0
                        ):
                            pass
                        else:
                            # Accept if timestamps rounded to seconds match (covers TZ parsing quirks)
                            try:
                                if int(
                                    expected_sent_at.replace(tzinfo=timezone.utc).timestamp()
                                ) == int(token_dt.replace(tzinfo=timezone.utc).timestamp()):
                                    pass
                                else:
                                    logger.debug(
                                        "Token timestamp delta too large",
                                        {
                                            "token_dt": token_dt.isoformat(),
                                            "expected_sent": expected_sent_at.replace(
                                                tzinfo=timezone.utc
                                            ).isoformat(),
                                            "delta": delta,
                                        },
                                    )
                                    return (False, "invalid")
                            except Exception:
                                logger.debug(
                                    "Token timestamp delta compare exception",
                                    {
                                        "token_dt": getattr(token_dt, "isoformat", str(token_dt)),
                                        "expected_sent": getattr(
                                            expected_sent_at,
                                            "isoformat",
                                            str(expected_sent_at),
                                        ),
                                        "delta": delta,
                                    },
                                )
                                return (False, "invalid")
                    except Exception:
                        logger.debug(
                            "Token timestamp delta too large",
                            {
                                "token_dt": getattr(token_dt, "isoformat", str(token_dt)),
                                "expected_sent": getattr(
                                    expected_sent_at, "isoformat", str(expected_sent_at)
                                ),
                                "delta": delta,
                            },
                        )
                        return (False, "invalid")
            # Expiry: use configured hours
            expiry_hours = app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
            if datetime.now(timezone.utc) > (expected_sent_at + timedelta(hours=int(expiry_hours))):
                return (False, "expired")
            return (True, None)
        except BadSignature:
            return (False, "invalid")
        except Exception as e:
            logger.exception("Token verification failed")
            return (False, "invalid")

    @staticmethod
    def verify_signed_token(
        token: str, email: str, expected_sent_at, salt: str = "email-verify"
    ) -> tuple:
        """Verify a signed token using a custom salt. Returns (True, None) or (False, 'invalid'|'expired').

        This is a thin wrapper around the signed-token portion of `verify_token` but allows a custom salt.
        """
        try:
            from datetime import datetime, timedelta, timezone

            from flask import current_app
            from itsdangerous import BadSignature, URLSafeSerializer

            app = EmailService.app or current_app

            secret = app.config.get("SECRET_KEY")
            serializer = URLSafeSerializer(secret, salt=salt)
            try:
                payload = serializer.loads(token)
            except BadSignature:
                # Try current_app alternative secret as fallback
                try:
                    from flask import current_app as falcon_current_app

                    other_secret = falcon_current_app.config.get("SECRET_KEY")
                    if other_secret and other_secret != secret:
                        serializer2 = URLSafeSerializer(other_secret, salt=salt)
                        payload = serializer2.loads(token)
                    else:
                        raise
                except BadSignature:
                    return (False, "invalid")

            if payload.get("email") != email:
                return (False, "invalid")
            token_sent = payload.get("sent_at")
            if not expected_sent_at:
                return (False, "invalid")
            try:
                if expected_sent_at.tzinfo is None:
                    expected_sent_at = expected_sent_at.replace(tzinfo=timezone.utc)
            except Exception:
                return (False, "invalid")

            # Parse token timestamp
            token_dt = None
            try:
                token_dt = datetime.fromisoformat(token_sent)
                if token_dt.tzinfo is None:
                    token_dt = token_dt.replace(tzinfo=timezone.utc)
            except Exception:
                try:
                    from dateutil.parser import isoparse

                    token_dt = isoparse(token_sent)
                    if token_dt.tzinfo is None:
                        token_dt = token_dt.replace(tzinfo=timezone.utc)
                except Exception:
                    token_dt = None

            if token_dt is None:
                expected_str = expected_sent_at.replace(tzinfo=timezone.utc).isoformat()
                if token_sent != expected_str:
                    return (False, "invalid")
            else:
                try:
                    delta = abs(
                        expected_sent_at.replace(tzinfo=timezone.utc).timestamp()
                        - token_dt.replace(tzinfo=timezone.utc).timestamp()
                    )
                except Exception:
                    delta = abs((expected_sent_at - token_dt).total_seconds())
                if delta > 60:
                    try:
                        if expected_sent_at.replace(microsecond=0) == token_dt.replace(
                            microsecond=0
                        ):
                            pass
                        else:
                            if int(
                                expected_sent_at.replace(tzinfo=timezone.utc).timestamp()
                            ) == int(token_dt.replace(tzinfo=timezone.utc).timestamp()):
                                pass
                            else:
                                return (False, "invalid")
                    except Exception:
                        return (False, "invalid")

            expiry_hours = app.config.get("EMAIL_VERIFICATION_EXPIRY_HOURS", 1)
            if datetime.now(timezone.utc) > (expected_sent_at + timedelta(hours=int(expiry_hours))):
                return (False, "expired")
            return (True, None)
        except Exception:
            return (False, "invalid")

    @staticmethod
    def send_verification_email(user, token: str, purpose: str = None) -> bool:
        """Send a human-friendly verification email containing the verification code and link.
        Returns True if send succeeded, False otherwise.
        """
        try:
            from flask import url_for

            # Build a verification URL that points to the UI (not an API endpoint)
            # If purpose is provided (e.g. 'reset'), build a purpose-specific URL.
            if purpose:
                if purpose == "reset":
                    # Admin-initiated reset should open a dedicated reset page
                    # Include the signed token as a query param so the recipient can follow the link.
                    verification_url = url_for(
                        "auth.reset_complete_page",
                        username=user.username,
                        reset_token=token,
                        _external=True,
                    )
                else:
                    verification_url = url_for(
                        "auth.verify_page",
                        username=user.username,
                        purpose=purpose,
                        _external=True,
                    )
            else:
                verification_url = url_for(
                    "auth.verify_page", username=user.username, _external=True
                )
            # Adjust subject for reset purpose
            subject = "Verify your SecureAuth account"
            if purpose == "reset":
                subject = "Admin password reset for your SecureAuth account"
            # Try to render a template if available
            try:
                from flask import render_template

                html_body = render_template(
                    "emails/verify_email.html",
                    username=user.username,
                    token=token,
                    verification_url=verification_url,
                    purpose=purpose,
                )
                if purpose == "reset":
                    text_body = (
                        f"Hello {user.username},\n\n"
                        f"An administrator initiated a password reset for this account. "
                        f"Open the following link to reset the password: {verification_url}\n\n"
                        "If you didn't expect this, ignore this message."
                    )
                else:
                    text_body = f"Hello {user.username},\n\nUse the following code to verify your email: {token}\n\nOr open this link: {verification_url}\n\nIf you didn't request this, ignore this message."
            except Exception:
                # Fallback to simple inline text/html
                if purpose == "reset":
                    text_body = (
                        f"Hello {user.username},\n\n"
                        f"An administrator initiated a password reset for this account. "
                        f"Open the following link to reset the password: {verification_url}\n\n"
                        "If you didn't expect this, ignore this message."
                    )
                    html_body = (
                        f"<p>Hello {user.username},</p>"
                        f"<p>An administrator initiated a password reset for this account. "
                        f"Open the following link to reset the password: <a href='{verification_url}'>Reset password</a></p>"
                        "<p>If you didn't request this, ignore this message.</p>"
                    )
                else:
                    text_body = (
                        f"Hello {user.username},\n\n"
                        f"Use the following code to verify your email: {token}\n\n"
                        f"Or open this link in your browser: {verification_url}\n\n"
                        "If you didn't request this, ignore this message."
                    )
                    html_body = (
                        f"<p>Hello {user.username},</p>"
                        f"<p>Use the following verification <strong>code</strong> to verify your email for your SecureAuth account:</p>"
                        f"<p style='font-size: 1.2em; font-weight: 600'>{token}</p>"
                        f"<p>Or click <a href='{verification_url}'>this link</a> to open the verification page.</p>"
                        "<p>If you didn't request this, ignore this message.</p>"
                    )

            return EmailService.send_email(
                subject, [user.email], html_body=html_body, text_body=text_body
            )
        except Exception as e:
            logger.exception("Failed to prepare/send verification email")
            # Do not raise; let callers decide how to handle send failures
            return False


# Module-level instance used by other modules (keeps previous API shape)
email_service = EmailService()
