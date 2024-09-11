from collections import defaultdict
import imaplib
import email
from email.policy import default
from datetime import datetime, timedelta, timezone

import base64
from io import BytesIO
import re
from PIL import Image
import boto3
from django.conf import settings

def generate_file_key(*args):
    return '-'.join(*args)

def upload_image_to_s3(byte_string, file_keys):
    file_name = generate_file_key(file_keys) + '.png'

    # AWS S3 클라이언트 생성
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    # byte string을 이미지로 변환
    image_data = base64.b64decode(byte_string)
    image = Image.open(BytesIO(image_data))
    
    # 이미지를 BytesIO에 저장
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    buffer.seek(0)
    
    # S3 버킷에 이미지 업로드
    s3.put_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=file_name,
        Body=buffer,
        ContentType='image/png'
    )

def generate_presigned_url(file_keys, expiration=settings.AWS_PRESIGNED_EXPIRATION):
    file_name = generate_file_key(file_keys) + '.png'

    # AWS S3 클라이언트 생성
    s3 = boto3.client(
        's3',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION_NAME
    )
    
    # presigned URL 생성
    try:
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': file_name
            },
            ExpiresIn=expiration  # URL 만료 시간 (초 단위)
        )
        return presigned_url
    except Exception as e:
        print(f"Error generating presigned URL: {e}")
        return None
    

def parse_userinfo(userinfo_obj):
    return {
        'user_id': userinfo_obj.id,
        'user_type': userinfo_obj.user_type if userinfo_obj.user_type else 'N/A',
        'user_name': userinfo_obj.username,
        'created_dt': userinfo_obj.created_dt,
        'year': userinfo_obj.year if userinfo_obj.year else -1,
        'school_id': userinfo_obj.school_id if userinfo_obj.school_id else -1,
        'school_name': userinfo_obj.school.school_name if userinfo_obj.school else 'N/A',
        'student_grade': userinfo_obj.student_grade if userinfo_obj.student_grade else -1,
        'student_class': userinfo_obj.student_class if userinfo_obj.student_class else -1,
        'student_number': userinfo_obj.student_number if userinfo_obj.student_number else -1,
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


def extract_digits(text):
    return re.search(r'\d+', text).group()
