import logging
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import NotFound

# 로거 설정
logger = logging.getLogger(__name__)


# 허용된 IP 주소만 접근 가능한 Permission + 로깅
class IsAllowedIP(BasePermission):
    def has_permission(self, request, view):
        ip = request.META.get('REMOTE_ADDR')
        path = request.path  # 요청 경로
        response_code = 404  # 응답 코드

        # IP 주소가 192.168.0.1 ~ 192.168.0.254 범위에 있는지 확인 - 사내 내부 IP
        if ip.startswith('192.168.0.') and 1 <= int(ip.split('.')[-1]) <= 254:
            return True
        # Docker 내부 IP, 프로메테우스 172.21.0.2
        elif ip.startswith('172.21.0.') and 1 <= int(ip.split('.')[-1]) <= 254:
            return True

        elif ip == '14.46.152.143':  # 회사 공인IP
            return True

        elif ip == '127.0.0.1':  # 테스트용 로컬 IP는 허용
            return True

        # 허용되지 않은 IP일 경우 로깅 및 404 Page not found 에러 발생
        logger.warning(f"Unauthorized access attempt: {path}, {response_code}, IP Addr: {ip}")  # IP 로깅
        # raise AuthenticationFailed("Unauthorized access")  # 401 Unauthorized 에러 발생
        raise NotFound("Page not found")  # 404 page not found 에러 발생