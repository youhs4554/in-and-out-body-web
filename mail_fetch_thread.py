import os
import django
import time

from mysite import settings

# Django 설정 파일 경로 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

# Django 환경 초기화
django.setup()

from datetime import datetime, timedelta, timezone
import imaplib
import email
from email.policy import default
import time

from analysis.models import AuthInfo

def fetch_recent_mails(email_host, email_user, email_password, minutes=1):
    # Connect to the email server
    mail = imaplib.IMAP4_SSL(email_host)
    mail.login(email_user, email_password)

    mail.select('inbox')

    # Calculate the time window for emails
    kst = timezone(timedelta(hours=9))  # Korean Standard Time (UTC+9)
    end_time = datetime.now(kst)
    start_time = end_time - timedelta(minutes=minutes)

    # Format times for IMAP search query
    since_time = start_time.strftime('%d-%b-%Y %H:%M:%S')

    fetched_data = []

    # Search for emails received within the last 'minutes' minutes
    result, data = mail.uid('search', None, f'(SINCE "{since_time}")')
    if result == 'OK':
        all_email = data[0].split()
        for uid in all_email:
            result, msg_data = mail.uid('fetch', uid, '(RFC822)')

            if result == 'OK':
                msg = email.message_from_bytes(msg_data[0][1], policy=default)

                # Extract the email's date
                email_date = email.utils.parsedate_to_datetime(msg['Date'])
                if email_date is None:
                    continue
                
                # Ensure the email's date is within the last minute
                if not (start_time <= email_date <= end_time):
                    continue

                sender = msg['From'].replace('<', '').replace('>', '').replace('"', '')
                sender_domain = sender.split('@')[-1].strip()
                sender = sender.replace('@' + sender_domain, '')

                # **Extract the body of the email (instead of the subject)**
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        # Check if the part is text/plain or text/html
                        if part.get_content_type() == "text/plain" and not part.get('Content-Disposition'):
                            body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                            break
                else:
                    body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')

                # Check if the sender's domain is in the allowed list
                # Extract the subject of the email
                mobile_uid = body.split('\n')[0].strip()
                phone_number = str(sender.split(' ')[0])
                fetched_data.append([mobile_uid, phone_number])

    # Cleanup
    mail.logout()

    return fetched_data


if __name__ == '__main__':
    email_host = settings.EMAIL_HOST
    email_user = settings.EMAIL_USER
    email_password = settings.EMAIL_PASSWORD


    while True:
        result = fetch_recent_mails(email_host, email_user, email_password, minutes=1)

        print(result)

        for uid, phone_number in result:
            AuthInfo.objects.update_or_create(phone_number=phone_number,
                                              defaults=dict(uid=uid))
        time.sleep(5)
