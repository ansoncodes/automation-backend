"""
core/auth_views.py

Authentication views for the SMEC sales dashboard.

Endpoints:
  POST /api/auth/login/  — exchange username + password for an auth token

This is the only auth endpoint needed: the dashboard uses token-based auth
(Authorization: Token <token>) for all subsequent requests. There is no
session, no cookie, and no refresh token — tokens are long-lived by default
(DRF authtoken behaviour). Revoke by deleting the token from the admin.
"""

import logging

from django.contrib.auth import authenticate

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


class LoginView(APIView):
    """
    Trade a valid username + password for an auth token.

    Authentication: none — this endpoint is itself the auth gate.
    On success  → 200 { "token": "...", "username": "..." }
    On failure  → 400 { "error": "Invalid credentials" }
    """

    # Public — no token required to reach the login endpoint itself
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        """
        Validate credentials and return (or create) the user's auth token.

        DRF's Token.objects.get_or_create() is used so that repeated logins
        return the same token rather than rotating it. To force a token
        rotation, delete the token record from the admin panel.
        """
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")

        # Basic presence check before hitting the auth backend
        if not username or not password:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Django's authenticate() checks the password against the hashed value
        user = authenticate(request, username=username, password=password)

        if user is None:
            logger.warning("Failed login attempt for username: %s", username)
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Inactive users must not receive a token
        if not user.is_active:
            logger.warning("Login attempt by inactive user: %s", username)
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # get_or_create so the same token is returned on repeated logins
        token, _ = Token.objects.get_or_create(user=user)

        logger.info("Successful login for user: %s", username)

        return Response(
            {"token": token.key, "username": user.username},
            status=status.HTTP_200_OK,
        )
