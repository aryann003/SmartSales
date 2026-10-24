from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView


class LoginRateThrottle(AnonRateThrottle):
    """Limit login attempts per IP to slow down password guessing."""

    scope = "login"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]
