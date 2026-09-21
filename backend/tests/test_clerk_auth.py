"""
Unit Tests for Nexa AI Enterprise V2 Clerk Authentication (Security Correction)
================================================================================
Verifies:
- NO Authorization header -> None (legitimate guest request)
- Malformed Authorization header -> HTTPException(status_code=401)
- Invalid / expired / tampered Clerk token -> HTTPException(status_code=401)
- Valid Clerk token -> authenticated user { "id": clerk_user_id, "email": email }
- Email fallback via Clerk User API when email claim is not in token payload
- Configured authorized parties support localhost development and extensible Vercel environments
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
import clerk_backend_api.security.types as ct

from app.auth.clerk_auth import get_current_user_optional, get_authenticate_options


class DummyRequest:
    """Mock HTTP Request with headers mapping."""
    def __init__(self, headers=None):
        self.headers = headers or {}


class TestClerkAuthSecurity(unittest.TestCase):

    def test_no_authorization_header_returns_none(self):
        """No Authorization header must return None (legitimate guest request)."""
        # 1. None request
        self.assertIsNone(get_current_user_optional(None))

        # 2. Empty headers dictionary
        req_empty = DummyRequest({})
        self.assertIsNone(get_current_user_optional(req_empty))

        # 3. Other headers present without Authorization
        req_other = DummyRequest({"Content-Type": "application/json", "User-Agent": "test"})
        self.assertIsNone(get_current_user_optional(req_other))

    def test_malformed_auth_header_raises_401(self):
        """Malformed Authorization header must raise 401 Unauthorized."""
        # 1. Non-Bearer scheme (e.g. Basic)
        req_basic = DummyRequest({"Authorization": "Basic dXNlcjpwYXNz"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req_basic)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Expected Bearer scheme", ctx.exception.detail)

        # 2. Missing token after Bearer
        req_empty_bearer = DummyRequest({"Authorization": "Bearer "})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req_empty_bearer)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("token is missing", ctx.exception.detail.lower())

        # 3. Empty string header value
        req_empty = DummyRequest({"Authorization": ""})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req_empty)
        self.assertEqual(ctx.exception.status_code, 401)

        # 4. Whitespace only
        req_space = DummyRequest({"Authorization": "   "})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req_space)
        self.assertEqual(ctx.exception.status_code, 401)

    @patch("app.auth.clerk_auth.get_clerk_client")
    def test_invalid_or_expired_token_raises_401(self, mock_get_client):
        """Invalid or expired Clerk token must raise 401 Unauthorized."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_state = ct.RequestState(
            status=ct.AuthStatus.SIGNED_OUT,
            reason=ct.TokenVerificationErrorReason.TOKEN_INVALID,
            token=None,
            payload=None
        )
        mock_client.authenticate_request.return_value = mock_state

        req = DummyRequest({"Authorization": "Bearer invalid.expired.token"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("Invalid or expired authentication token", ctx.exception.detail)
        mock_client.authenticate_request.assert_called_once()

    @patch("app.auth.clerk_auth.get_clerk_client")
    def test_sdk_exception_raises_401(self, mock_get_client):
        """Exceptions during Clerk verification must raise 401 Unauthorized."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.authenticate_request.side_effect = RuntimeError("Token signature verification failed")

        req = DummyRequest({"Authorization": "Bearer tampered.signature.token"})
        with self.assertRaises(HTTPException) as ctx:
            get_current_user_optional(req)

        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("verification failed", ctx.exception.detail.lower())

    @patch("app.auth.clerk_auth.get_clerk_client")
    def test_valid_token_with_email_in_claims(self, mock_get_client):
        """Valid Clerk token with email claim returns authenticated user info."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_state = ct.RequestState(
            status=ct.AuthStatus.SIGNED_IN,
            payload={
                "sub": "user_29w83sxm10pq",
                "email": "piyush@enterprise.com",
            },
            token="valid.jwt.token"
        )
        mock_client.authenticate_request.return_value = mock_state

        req = DummyRequest({"Authorization": "Bearer valid.jwt.token"})
        result = get_current_user_optional(req)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "user_29w83sxm10pq")
        self.assertEqual(result["email"], "piyush@enterprise.com")

    @patch("app.auth.clerk_auth.settings")
    @patch("app.auth.clerk_auth.get_clerk_client")
    def test_valid_token_with_user_api_email_fallback(self, mock_get_client, mock_settings):
        """Valid Clerk token without email claim falls back to Clerk User API."""
        mock_settings.CLERK_SECRET_KEY = "sk_test_mock_secret_key"
        mock_settings.CLERK_AUTHORIZED_PARTIES = ["http://localhost:5173"]

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_state = ct.RequestState(
            status=ct.AuthStatus.SIGNED_IN,
            payload={"sub": "user_abc987"},
            token="valid.jwt.noemail"
        )
        mock_client.authenticate_request.return_value = mock_state

        mock_email_obj = MagicMock()
        mock_email_obj.id = "email_123"
        mock_email_obj.email_address = "fallback@nexa.ai"

        mock_user = MagicMock()
        mock_user.primary_email_address_id = "email_123"
        mock_user.email_addresses = [mock_email_obj]
        mock_client.users.get.return_value = mock_user

        req = DummyRequest({"Authorization": "Bearer valid.jwt.noemail"})
        result = get_current_user_optional(req)

        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "user_abc987")
        self.assertEqual(result["email"], "fallback@nexa.ai")
        mock_client.users.get.assert_called_once_with(user_id="user_abc987")

    def test_authorized_parties_configuration(self):
        """AuthenticateRequestOptions contains configured authorized parties."""
        opts = get_authenticate_options()
        self.assertIsNotNone(opts.authorized_parties)
        self.assertIn("http://localhost:5173", opts.authorized_parties)


if __name__ == "__main__":
    unittest.main()
