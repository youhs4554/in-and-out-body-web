from django.test import SimpleTestCase, TestCase
from django.urls import reverse, resolve
from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.hashers import make_password
from .models import AuthInfo, UserInfo
from . import views, views_mobile

base_url = 'http://localhost:8000/'
mobile_uid = 'qwer'
phone_number = '01012345678'
password = '1234'
kiosk_id = 'jifjaeijfieajfi'

class UrlsTestCase(SimpleTestCase):
    
    def test_home_url(self):
        url = reverse('home')
        self.assertEqual(resolve(url).func, views.home)

    def test_login_url(self):
        url = reverse('login')
        self.assertEqual(resolve(url).func.view_class, auth_views.LoginView)

    def test_register_url(self):
        url = reverse('register')
        self.assertEqual(resolve(url).func, views.register)

    def test_report_url(self):
        url = reverse('report')
        self.assertEqual(resolve(url).func, views.report)

    def test_policy_url(self):
        url = reverse('policy')
        self.assertEqual(resolve(url).func, views.policy)

    def test_logout_url(self):
        url = reverse('logout')
        self.assertEqual(resolve(url).func.view_class, auth_views.LogoutView)

    def test_password_change_url(self):
        url = reverse('password_change')
        self.assertEqual(resolve(url).func.view_class, views.CustomPasswordChangeView)

    def test_password_change_done_url(self):
        url = reverse('password_change_done')
        self.assertEqual(resolve(url).func.view_class, auth_views.PasswordChangeDoneView)

    def test_token_obtain_pair_url(self):
        url = reverse('token_obtain_pair')
        self.assertEqual(resolve(url).func.view_class, TokenObtainPairView)

    def test_token_refresh_url(self):
        url = reverse('token_refresh')
        self.assertEqual(resolve(url).func.view_class, TokenRefreshView)

    def test_request_auth_url(self):
        url = reverse('mobile-auth-request_auth')
        self.assertEqual(resolve(url).func, views_mobile.login_mobile)

    def test_login_kiosk_url(self):
        url = reverse('login_kiosk')
        self.assertEqual(resolve(url).func, views.login_kiosk)

    def test_login_kiosk_id_url(self):
        url = reverse('login_kiosk_id')
        self.assertEqual(resolve(url).func, views.login_kiosk_id)

    def test_get_userinfo_session_url(self):
        url = reverse('get_userinfo_session')
        self.assertEqual(resolve(url).func, views.get_userinfo_session)

    def test_end_session_url(self):
        url = reverse('end_session')
        self.assertEqual(resolve(url).func, views.end_session)

class GaitResultTests(TestCase):
    def setUp(self):
        self.kiosk_client = APIClient()

        # Create the required objects
        self.auth_info = AuthInfo.objects.create(uid=mobile_uid, phone_number=phone_number)
        self.user_info = UserInfo.objects.create(
            username=phone_number,
            phone_number=phone_number,
            password=make_password(password)
        )

        # Authenticate and get access token
        auth_response = self.kiosk_client.post('/api/mobile/login-mobile/', {'mobile_uid': mobile_uid}, format='json')
        auth_data = auth_response.json()['data']
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        self.mobile_client = APIClient()
        self.mobile_client.credentials(HTTP_AUTHORIZATION='Bearer ' + auth_data['jwt_tokens']['access_token'])

        # Login to kiosk and get session key
        response = self.kiosk_client.post('/api/login-kiosk/', {'kiosk_id': kiosk_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session_key = response.data['data']['session_key']

        # Login mobile using QR code
        response = self.mobile_client.post('/api/mobile/login-mobile-qr/', {'session_key': self.session_key}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Login kiosk using ID and Password
        response = self.kiosk_client.post('/api/login-kiosk-id/', {'session_key': self.session_key, 'phone_number': phone_number, 'password': password}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

    def test_get_gait_result_success(self):
        # First, create a gait result
        self.kiosk_client.post(base_url + 'api/analysis/gait/create_result/', self.gait_data, format='json')

        # Case 1 : using jwt Tokens (mobile)
        response = self.mobile_client.get(base_url + 'api/analysis/gait/get_result/', {'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

        # Case 2 : using session_key (kiosk)
        response = self.kiosk_client.get(base_url + 'api/analysis/gait/get_result/', {'session_key': self.session_key, 'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_create_gait_result_missing_session_key(self):
        invalid_data = {'gait_data': self.gait_data['gait_data']}  # No session key provided
        response = self.kiosk_client.post(base_url + 'api/analysis/gait/create_result/', invalid_data, format='json')
        self.assertEqual(response.data['data']['message'], 'session_key_required')


class BodyResultTests(TestCase):
    def setUp(self):
        self.kiosk_client = APIClient()

        # Create the required objects
        self.auth_info = AuthInfo.objects.create(uid=mobile_uid, phone_number=phone_number)
        self.user_info = UserInfo.objects.create(
            username=phone_number,
            phone_number=phone_number,
            password=make_password(password)
        )

        # Authenticate and get access token
        auth_response = self.kiosk_client.post('/api/mobile/login-mobile/', {'mobile_uid': mobile_uid}, format='json')
        auth_data = auth_response.json()['data']
        self.assertEqual(auth_response.status_code, status.HTTP_200_OK)
        self.mobile_client = APIClient()
        self.mobile_client.credentials(HTTP_AUTHORIZATION='Bearer ' + auth_data['jwt_tokens']['access_token'])

        # Login to kiosk and get session key
        response = self.kiosk_client.post('/api/login-kiosk/', {'kiosk_id': kiosk_id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.session_key = response.data['data']['session_key']

        # Login mobile using QR code
        response = self.mobile_client.post('/api/mobile/login-mobile-qr/', {'session_key': self.session_key}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Login kiosk using ID and Password
        response = self.kiosk_client.post('/api/login-kiosk-id/', {'session_key': self.session_key, 'phone_number': phone_number, 'password': password}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

    def test_get_body_result_success(self):
        # First, create a body result
        self.kiosk_client.post(base_url + 'api/analysis/body/create_result/', self.body_data, format='json')

        # Case 1 : using jwt Tokens (mobile)
        response = self.mobile_client.get(base_url + 'api/analysis/body/get_result/', {'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

        # Case 2 : using session_key (kiosk)
        response = self.kiosk_client.get(base_url + 'api/analysis/body/get_result/', {'session_key': self.session_key, 'id': 1}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        self.assertIsInstance(response.data['data'], list)

    def test_create_body_result_missing_session_key(self):
        invalid_data = {'body_data': self.body_data['body_data']}  # No session key provided
        response = self.kiosk_client.post(base_url + 'api/analysis/body/create_result/', invalid_data, format='json')
        self.assertEqual(response.data['data']['message'], 'session_key_required')
