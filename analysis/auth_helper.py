import imaplib
import email
from email.policy import default
import time
from datetime import datetime, timedelta, timezone

def monitor_inbox(email_host, email_user, email_pass, requested_code, minutes=1, allowed_domains=["vmms.nate.com", "ktfmms.magicn.com", "lguplus.com"], check_interval=5):
    """
    Monitors the inbox for new emails from allowed domains and checks if the subject matches the requested code.

    :param email_host: The email server host (e.g., 'imap.naver.com')
    :param email_user: The email address to log in with
    :param email_pass: The password for the email account
    :param requested_code: The authentication code to match
    :param minutes: The number of minutes to look back for new emails
    :param allowed_domains: List of allowed sender domains
    :param check_interval: Time in seconds to wait between checks
    """
    # Connect to the email server
    mail = imaplib.IMAP4_SSL(email_host)
    mail.login(email_user, email_pass)

    # Initialize the last processed UID
    last_processed_uid = None

    try:
        while True:
            mail.select('inbox')

            # Calculate the time 'minutes' ago in Korean Standard Time (KST)
            kst = timezone(timedelta(hours=9))  # Korean Standard Time (UTC+9)
            since_time = (datetime.now(kst) - timedelta(minutes=minutes)).strftime('%d-%b-%Y')

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
                                return True, phone_number  # Return when a matching code is found
                    
                    # Update the last processed UID
                    last_processed_uid = uid
            
            # Wait before checking again
            time.sleep(check_interval)
    except KeyboardInterrupt:
        print("Stopping the inbox monitor.")
    finally:
        # Cleanup
        mail.logout()
