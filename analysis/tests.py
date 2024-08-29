from django.test import SimpleTestCase
from django.urls import reverse, resolve
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import home, register_student, report, policy, auth_mobile, login_kiosk, login_mobile_qr, login_kiosk_id, get_userinfo_session, end_session, CustomPasswordChangeView
from rest_framework.routers import DefaultRouter

class UrlsTestCase(SimpleTestCase):
    
    def test_home_url(self):
        url = reverse('home')
        self.assertEqual(resolve(url).func, home)

    def test_login_url(self):
        url = reverse('login')
        self.assertEqual(resolve(url).func.view_class, auth_views.LoginView)

    def test_register_student_url(self):
        url = reverse('register_student')
        self.assertEqual(resolve(url).func, register_student)

    def test_report_url(self):
        url = reverse('report')
        self.assertEqual(resolve(url).func, report)

    def test_policy_url(self):
        url = reverse('policy')
        self.assertEqual(resolve(url).func, policy)

    def test_logout_url(self):
        url = reverse('logout')
        self.assertEqual(resolve(url).func.view_class, auth_views.LogoutView)

    def test_password_change_url(self):
        url = reverse('password_change')
        self.assertEqual(resolve(url).func.view_class, CustomPasswordChangeView)

    def test_password_change_done_url(self):
        url = reverse('password_change_done')
        self.assertEqual(resolve(url).func.view_class, auth_views.PasswordChangeDoneView)

    def test_token_obtain_pair_url(self):
        url = reverse('token_obtain_pair')
        self.assertEqual(resolve(url).func.view_class, TokenObtainPairView)

    def test_token_refresh_url(self):
        url = reverse('token_refresh')
        self.assertEqual(resolve(url).func.view_class, TokenRefreshView)

    def test_auth_mobile_url(self):
        url = reverse('auth_mobile')
        self.assertEqual(resolve(url).func, auth_mobile)

    def test_login_kiosk_url(self):
        url = reverse('login_kiosk')
        self.assertEqual(resolve(url).func, login_kiosk)

    def test_login_mobile_qr_url(self):
        url = reverse('login_mobile_qr')
        self.assertEqual(resolve(url).func, login_mobile_qr)

    def test_login_kiosk_id_url(self):
        url = reverse('login_kiosk_id')
        self.assertEqual(resolve(url).func, login_kiosk_id)

    def test_get_userinfo_session_url(self):
        url = reverse('get_userinfo_session')
        self.assertEqual(resolve(url).func, get_userinfo_session)

    def test_end_session_url(self):
        url = reverse('end_session')
        self.assertEqual(resolve(url).func, end_session)


from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from .models import AuthInfo, SessionInfo, UserInfo, BodyResult, GaitResult
from rest_framework_simplejwt.tokens import RefreshToken
import uuid

base_url = 'http://localhost:8000/'

class MobileAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.mobile_uid = 'qwer'
        self.phone_number = '01053614549'
        self.password = '1234'
        self.auth_info = AuthInfo.objects.create(uid=self.mobile_uid, phone_number=self.phone_number)
        self.user_info = UserInfo.objects.create(
            username=self.phone_number,
            phone_number=self.phone_number,
            password=make_password(self.password)
        )

    def test_auth_mobile_success(self):
        response = self.client.post(base_url + 'api/auth-mobile/', {'mobile_uid': self.mobile_uid}, format='json')
        response_data = response.data['data']['data']
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('jwt_tokens', response_data)
        self.assertIn('access_token', response_data['jwt_tokens'])

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.hashers import make_password
from .models import AuthInfo, SessionInfo, UserInfo

class GaitResultTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.mobile_uid = 'qwer'
        self.phone_number = '01053614549'
        self.password = '1234'
        self.kiosk_id = 'test_kiosk_id'

        # Create the required objects
        self.auth_info = AuthInfo.objects.create(uid=self.mobile_uid, phone_number=self.phone_number)
        self.user_info = UserInfo.objects.create(
            username=self.phone_number,
            phone_number=self.phone_number,
            password=make_password(self.password)
        )

        # Authenticate and get access token
        auth_response = self.client.post('/api/auth-mobile/', {'mobile_uid': self.mobile_uid}, format='json')
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        access_token = auth_response.data['data']['data']['jwt_tokens']['access_token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

        # Login to kiosk and get session key
        kiosk_response = self.client.post('/api/login-kiosk/', {'kiosk_id': self.kiosk_id}, format='json')
        self.assertEqual(kiosk_response.status_code, status.HTTP_200_OK)
        self.session_key = kiosk_response.data['data']['session_key']

        # Login mobile using QR code
        kiosk_response = self.client.post('/api/login-mobile-qr/', {'session_key': self.session_key, 'user_id': self.user_info.id}, format='json')
        self.assertEqual(kiosk_response.status_code, status.HTTP_200_OK)
        self.session_key = kiosk_response.data['data']['session_key']

        # Prepare gait data
        self.gait_data = {
            'session_key': self.session_key,
            'gait_data': {
                'velocity': 1.0,
                'cadence': 100,
                'cycle_time_l': 0.5,
                'cycle_time_r': 0.5,
                'stride_len_l': 1.0,
                'stride_len_r': 1.0,
                'supp_base_l': 0.1,
                'supp_base_r': 0.1,
                'swing_perc_l': 0.6,
                'swing_perc_r': 0.6,
                'stance_perc_l': 0.4,
                'stance_perc_r': 0.4,
                'd_supp_perc_l': 0.2,
                'd_supp_perc_r': 0.2,
                'toeinout_l': 5,
                'toeinout_r': 5,
                'stridelen_cv_l': 0.01,
                'stridelen_cv_r': 0.01,
                'stridetm_cv_l': 0.01,
                'stridetm_cv_r': 0.01,
                'score': 85
            }
        }

    def test_create_gait_result_success(self):
        response = self.client.post(base_url + 'api/analysis/gait/create_result/', self.gait_data, format='json')
        self.assertEqual(response.data['message'], 'created_gait_result')

    def test_get_gait_result_success(self):
        # First, create a gait result
        self.client.post(base_url + 'api/analysis/gait/create_result/', self.gait_data, format='json')

        # Then, retrieve it
        response = self.client.get(base_url + 'api/analysis/gait/get_result/', {'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_create_gait_result_missing_session_key(self):
        invalid_data = {'gait_data': self.gait_data['gait_data']}  # No session key provided
        response = self.client.post(base_url + 'api/analysis/gait/create_result/', invalid_data, format='json')
        self.assertEqual(response.data['message'], 'session_key_required')


class BodyResultTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.mobile_uid = 'qwer'
        self.phone_number = '01053614549'
        self.password = '1234'
        self.kiosk_id = 'test_kiosk_id'

        # Create the required objects
        self.auth_info = AuthInfo.objects.create(uid=self.mobile_uid, phone_number=self.phone_number)
        self.user_info = UserInfo.objects.create(
            username=self.phone_number,
            phone_number=self.phone_number,
            password=make_password(self.password)
        )

        # Authenticate and get access token
        auth_response = self.client.post('/api/auth-mobile/', {'mobile_uid': self.mobile_uid}, format='json')
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        access_token = auth_response.data['data']['data']['jwt_tokens']['access_token']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + access_token)

        # Login to kiosk and get session key
        kiosk_response = self.client.post('/api/login-kiosk/', {'kiosk_id': self.kiosk_id}, format='json')
        self.assertEqual(kiosk_response.status_code, status.HTTP_200_OK)
        self.session_key = kiosk_response.data['data']['session_key']

        # Login mobile using QR code
        kiosk_response = self.client.post('/api/login-mobile-qr/', {'session_key': self.session_key, 'user_id': self.user_info.id}, format='json')
        self.assertEqual(kiosk_response.status_code, status.HTTP_200_OK)
        self.session_key = kiosk_response.data['data']['session_key']

        # Prepare body data
        self.body_data = {
            'session_key': self.session_key,
            'body_data': {
                'face_level_angle': 1.0,
                'shoulder_level_angle': 2.0,
                'hip_level_angle': 3.0,
                'leg_length_ratio': 1.5,
                'left_leg_alignment_angle': 4.0,
                'right_leg_alignment_angle': 5.0,
                'left_back_knee_angle': 6.0,
                'right_back_knee_angle': 7.0,
                'forward_head_angle': 8.0,
                'scoliosis_shoulder_ratio': 1.1,
                'scoliosis_hip_ratio': 1.2,
            }
        }

    def test_create_body_result_success(self):
        response = self.client.post(base_url + 'api/analysis/body/create_result/', self.body_data, format='json')
        self.assertEqual(response.data['message'], 'created_body_result')

    def test_get_body_result_success(self):
        # First, create a body result
        self.client.post(base_url + 'api/analysis/body/create_result/', self.body_data, format='json')

        # Then, retrieve it
        response = self.client.get(base_url + 'api/analysis/body/get_result/', {'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print(response.data)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_create_body_result_missing_session_key(self):
        invalid_data = {'body_data': self.body_data['body_data']}  # No session key provided
        response = self.client.post(base_url + 'api/analysis/body/create_result/', invalid_data, format='json')
        self.assertEqual(response.data['message'], 'session_key_required')
