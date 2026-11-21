from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import get_role


class LoginView(APIView):
    """Login for Admin, HR and Employee users."""

    permission_classes = [AllowAny]

    # Ignore any old or invalid token sent by the browser,
    # otherwise a stale token makes the login request fail with 401.
    authentication_classes = []

    def post(self, request):

        user = authenticate(
            username=request.data.get("username"),
            password=request.data.get("password")
        )

        if user is None:
            return Response(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        role = get_role(user)

        if role is None:
            return Response(
                {"message": "Your account has no role. Ask the administrator."},
                status=status.HTTP_403_FORBIDDEN
            )

        employee = getattr(user, "employee_profile", None)
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            "message": "Login successful",
            "token": token.key,
            "username": user.username,
            "role": role,
            "employee_id": employee.id if employee else None,
            "employee_name": employee.name if employee else None,
        })


class LogoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "Logout successful"})