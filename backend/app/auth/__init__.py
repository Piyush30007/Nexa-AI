"""
Authentication module for Nexa AI Enterprise.
Exposes Clerk authentication utilities.
"""
from app.auth.clerk_auth import get_current_user_optional, get_clerk_client

__all__ = ["get_current_user_optional", "get_clerk_client"]
