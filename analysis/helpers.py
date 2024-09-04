from collections import defaultdict
import imaplib
import email
from email.policy import default
import time
from datetime import datetime, timedelta, timezone
import threading

class TimeoutException(Exception):
    pass

def parse_userinfo(userinfo_obj):
    return {
        'user_id': userinfo_obj.id,
        'user_type': userinfo_obj.user_type if userinfo_obj.user_type else 'N/A',
        'user_name': userinfo_obj.username,
        'created_dt': userinfo_obj.created_dt,
        'year': userinfo_obj.year if userinfo_obj.year else 'N/A',
        'school_id': userinfo_obj.school_id if userinfo_obj.school_id else 'N/A',
        'school_name': userinfo_obj.school.school_name if userinfo_obj.school else 'N/A',
        'student_grade': userinfo_obj.student_grade if userinfo_obj.student_grade else 'N/A',
        'student_class': userinfo_obj.student_class if userinfo_obj.student_class else 'N/A',
        'student_number': userinfo_obj.student_number if userinfo_obj.student_number else 'N/A',
        'student_name': userinfo_obj.student_name if userinfo_obj.student_name else 'N/A',
        'phone_number': userinfo_obj.phone_number if userinfo_obj.phone_number else 'N/A',
    }


def fetch_recent_mails(email_host, email_user, email_password, minutes=1, allowed_domains=["vmms.nate.com", "ktfmms.magicn.com", "mmsmail.uplus.co.kr", "lguplus.com"]):
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

    fetched_data = defaultdict(list)

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

                # Check if the sender's domain is in the allowed list
                if sender_domain in allowed_domains:
                    # Extract the subject of the email
                    mobile_uid = str(msg['Subject'])
                    phone_number = str(sender.split(' ')[0])
                    fetched_data['uid'].append(mobile_uid)
                    fetched_data['phone_number'].append(phone_number)

    # Cleanup
    mail.logout()

    return fetched_data


def monitor_inbox(email_host, email_user, email_password, requested_code, minutes=1, allowed_domains=["vmms.nate.com", "ktfmms.magicn.com", "mmsmail.uplus.co.kr", "lguplus.com"], check_interval=5, timeout=60):
    """
    Monitors the inbox for new emails from allowed domains and checks if the subject matches the requested code.

    :param email_host: The email server host (e.g., 'imap.naver.com')
    :param email_user: The email address to log in with
    :param email_password: The password for the email account
    :param requested_code: The authentication code to match
    :param minutes: The number of minutes to look back for new emails (for monitoring purposes, should be 1)
    :param allowed_domains: List of allowed sender domains
    :param check_interval: Time in seconds to wait between checks
    :param timeout: Timeout period in seconds
    :return: A tuple (bool, str) indicating whether the code was found and the phone number
    """
    # Connect to the email server
    mail = imaplib.IMAP4_SSL(email_host)
    mail.login(email_user, email_password)

    # Initialize the last processed UID
    last_processed_uid = None
    is_authorized = False
    authorized_phone_number = None


    def monitor():
        nonlocal last_processed_uid, is_authorized, authorized_phone_number
        try:
            while True:
                mail.select('inbox')

                # Calculate the time window for emails
                kst = timezone(timedelta(hours=9))  # Korean Standard Time (UTC+9)
                end_time = datetime.now(kst)
                start_time = end_time - timedelta(minutes=minutes)

                # Format times for IMAP search query
                since_time = start_time.strftime('%d-%b-%Y %H:%M:%S')

                # Search for emails received within the last 'minutes' minutes
                result, data = mail.uid('search', None, f'(SINCE "{since_time}")')
                if result == 'OK':
                    email_uids = data[0].split()

                    if last_processed_uid:
                        # Filter out the emails that have already been processed
                        new_email_uids = [uid for uid in email_uids if int(uid) > int(last_processed_uid)]
                    else:
                        # If no emails have been processed, consider all new emails
                        new_email_uids = email_uids

                    for uid in new_email_uids:
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

                            # Check if the sender's domain is in the allowed list
                            if sender_domain in allowed_domains:
                                # Extract the subject of the email
                                subject = str(msg['Subject'])
                                phone_number = str(sender.split(' ')[0])

                                print(f'[{uid}] subject : {subject}[{type(subject)}], requested_code : {requested_code}[{type(requested_code)}], is_auth: {subject == requested_code}')
                                # Check if the subject matches the requested code
                                if subject == requested_code:
                                    print(f"전화 번호 : [{phone_number}], 인증 번호 : {subject}")
                                    is_authorized = True
                                    authorized_phone_number = phone_number
                                    return

                        # Update the last processed UID
                        last_processed_uid = uid

                # Wait before checking again
                time.sleep(check_interval)
        except TimeoutException:
            print("Timeout occurred. Stopping the inbox monitor.")
        except KeyboardInterrupt:
            print("Stopping the inbox monitor.")
        finally:
            # Cleanup
            mail.logout()

    # Create a thread for monitoring
    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()

    # Wait for the timeout period
    monitor_thread.join(timeout)

    # Check if the thread is still alive after the timeout period
    if monitor_thread.is_alive():
        raise TimeoutException("Monitoring timed out.")

    # If monitoring finishes without timeout, return
    return is_authorized, authorized_phone_number
