import os
from dotenv import load_dotenv
import smtplib

# Load .env from project root
here = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(here, '.env'))

srv = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
port = int(os.getenv('MAIL_PORT', '587'))
tls = os.getenv('MAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes')
ssl = os.getenv('MAIL_USE_SSL', 'False').lower() in ('1', 'true', 'yes')
user = os.getenv('MAIL_USERNAME')
pwd = os.getenv('MAIL_PASSWORD')

print('Using SMTP server:', srv)
print('PORT:', port, 'TLS:', tls, 'SSL:', ssl)
print('USERNAME:', user)
print('PASSWORD LENGTH:', len(pwd) if pwd else 0)

try:
    if ssl:
        conn = smtplib.SMTP_SSL(srv, port, timeout=10)
    else:
        conn = smtplib.SMTP(srv, port, timeout=10)
    conn.set_debuglevel(1)
    conn.ehlo()
    if tls and not ssl:
        conn.starttls()
        conn.ehlo()
    try:
        conn.login(user, pwd)
        print('\nSMTP login OK')
    except Exception as e:
        print('\nSMTP login FAILED:', repr(e))
    finally:
        try:
            conn.quit()
        except Exception:
            pass
except Exception as e:
    print('\nConnection error:', repr(e))
