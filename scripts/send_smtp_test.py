"""Send a small test email using current Flask-Mail config.
Usage: python scripts/send_smtp_test.py --to you@example.com
"""

import argparse

from app import create_app
from app.services.email_service import EmailService, email_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", "-t", required=True, help="Recipient email")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        EmailService.init_mail(app)
        ok = email_service.send_email(
            "SecureAuth SMTP Test",
            [args.to],
            text_body="This is a test email from SecureAuth.",
        )
        if ok:
            print("Test email sent (check your inbox).")
        else:
            print("Failed to send test email. Check configuration and logs.")


if __name__ == "__main__":
    main()
