from typing import Optional, Dict, Any, List
from fastapi import Request, HTTPException, Depends
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from app.config import settings
import logfire


def get_clerk_client(secret_key: Optional[str] = None) -> Clerk:
    """
    Factory function to get or instantiate a Clerk client.
    """
    key = secret_key if secret_key is not None else settings.CLERK_SECRET_KEY
    return Clerk(bearer_auth=key or "")


def get_authenticate_options() -> AuthenticateRequestOptions:
    """
    Build AuthenticateRequestOptions with configured authorized parties
    supporting localhost development and extensible Vercel/production environments.
    """
    authorized_parties: Optional[List[str]] = (
        getattr(settings, "CLERK_AUTHORIZED_PARTIES", None) or None
    )
    return AuthenticateRequestOptions(authorized_parties=authorized_parties)


def get_current_user_optional(request: Request) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to authenticate Clerk users.

    Behavior:
    1. NO Authorization header:
       -> return None (legitimate guest request).
    2. Authorization header exists but is malformed (not Bearer, empty token, etc.):
       -> raise HTTPException(status_code=401)
    3. Authorization header contains an invalid/expired/tampered Clerk token:
       -> raise HTTPException(status_code=401)
    4. Valid Clerk token:
       -> return {"id": clerk_user_id, "email": email}
    """
    if request is None or not hasattr(request, "headers"):
        return None

    headers = request.headers
    # Case-insensitive lookup for Authorization header
    auth_header = None
    for k, v in headers.items():
        if k.lower() == "authorization":
            auth_header = v
            break

    # 1. NO Authorization header -> legitimate guest request
    if auth_header is None:
        return None

    # 2. Authorization header exists but is malformed
    if not isinstance(auth_header, str) or not auth_header.strip():
        raise HTTPException(
            status_code=401,
            detail="Malformed authorization header. Header value cannot be empty.",
        )

    clean_header = auth_header.strip()
    if not clean_header.lower().startswith("bearer"):
        raise HTTPException(
            status_code=401,
            detail="Malformed authorization header. Expected Bearer scheme ('Bearer <token>').",
        )

    parts = clean_header.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        raise HTTPException(
            status_code=401,
            detail="Malformed authorization header. Bearer token is missing.",
        )

    token = parts[1].strip()

    # 3. Authenticate token using official Clerk SDK
    try:
        client = get_clerk_client()
        options = get_authenticate_options()
        state = client.authenticate_request(request, options)

        if not state.is_signed_in:
            reason_msg = getattr(state, "message", None) or "Token is invalid, expired, or tampered."
            raise HTTPException(
                status_code=401,
                detail=f"Invalid or expired authentication token: {reason_msg}",
            )

        payload = state.payload or {}
        clerk_user_id = payload.get("sub")
        if not clerk_user_id and state.token:
            auth_obj = state.to_auth()
            clerk_user_id = getattr(auth_obj, "user_id", None)

        if not clerk_user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token payload: missing user identifier.",
            )

        email = payload.get("email")

        # Fallback to query Clerk User API for email if not present in token claims
        if not email and settings.CLERK_SECRET_KEY:
            try:
                user_obj = client.users.get(user_id=clerk_user_id)
                if user_obj and getattr(user_obj, "email_addresses", None):
                    primary_id = getattr(user_obj, "primary_email_address_id", None)
                    matched = None
                    if primary_id:
                        for e in user_obj.email_addresses:
                            if getattr(e, "id", None) == primary_id:
                                matched = getattr(e, "email_address", None)
                                break
                    email = matched or getattr(user_obj.email_addresses[0], "email_address", None)
            except Exception as ex:
                logfire.debug(f"Could not fetch user details from Clerk: {ex}")

        # 4. Valid Clerk token -> return authenticated user information
        return {
            "id": clerk_user_id,
            "email": email,
        }

    except HTTPException:
        raise
    except Exception as e:
        logfire.debug(f"Clerk authentication exception: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication token verification failed: {str(e)}",
        )


def get_current_user(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    FastAPI dependency requiring a valid authenticated Clerk user.
    Raises HTTP 401 if unauthenticated.
    """
    if not current_user or not current_user.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please sign in.",
        )
    return current_user
