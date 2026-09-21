"""
Conversation Persistence & Ownership Service (Phase 6.2A)
=========================================================
Handles conversation lookup, ownership enforcement, and persistence for
authenticated Clerk users while preserving existing stateless guest access.
"""

import uuid
from datetime import timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logfire

from database import Conversation, Message


def _format_utc_iso(dt: Any) -> str:
    """
    Ensures datetime is serialized to ISO-8601 with UTC timezone suffix ('Z')
    so that frontend parsers correctly interpret it as UTC and convert to local time.
    """
    if dt is None:
        return ""
    if hasattr(dt, "tzinfo"):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        iso = dt.astimezone(timezone.utc).isoformat()
        if iso.endswith("+00:00"):
            iso = iso[:-6] + "Z"
        return iso
    return str(dt)


def resolve_or_create_conversation(
    db: Session,
    conversation_id: Optional[str],
    current_user: Optional[Dict[str, Any]],
) -> str:
    """
    Enforces conversation ownership and persistence rules.

    1. Authenticated Requests (current_user is not None):
       - If conversation_id is provided:
         - Query database for existing Conversation.
         - If found:
           - Verify that conversation.user_id == current_user["id"].
           - If conversation.user_id != current_user["id"]:
             raise HTTPException(status_code=403, detail="Forbidden: You do not have access to this conversation.")
           - Return conversation.id.
         - If not found:
           - Create a new Conversation row with id=conversation_id, user_id=current_user["id"].
           - Commit to DB and return the conversation ID.
       - If conversation_id is not provided (None or empty):
         - Create a new Conversation row with user_id=current_user["id"] (auto-generating UUID id).
         - Commit to DB and return the generated conversation ID.

    2. Guest Requests (current_user is None):
       - Do NOT create a persistent Conversation row in the database.
       - If conversation_id is provided:
         - Check whether a conversation with this ID exists with an assigned user_id.
         - If an authenticated user owns this conversation, reject with HTTP 403.
         - Otherwise return the supplied conversation_id.
       - If conversation_id is not provided:
         - Generate a new UUID for this guest request (preserving ephemeral isolation without persisting to DB).
    """
    cleaned_id = conversation_id.strip() if conversation_id and isinstance(conversation_id, str) else None
    if cleaned_id == "":
        cleaned_id = None

    if current_user is not None:
        clerk_user_id = current_user.get("id")
        if not clerk_user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid user session: missing user identifier.",
            )

        if cleaned_id is not None:
            existing = db.query(Conversation).filter(Conversation.id == cleaned_id).first()
            if existing is not None:
                if existing.user_id != clerk_user_id:
                    raise HTTPException(
                        status_code=403,
                        detail="Forbidden: You do not have access to this conversation.",
                    )
                return existing.id
            else:
                new_conv = Conversation(
                    id=cleaned_id,
                    user_id=clerk_user_id,
                )
                db.add(new_conv)
                db.commit()
                db.refresh(new_conv)
                return new_conv.id
        else:
            new_conv = Conversation(
                user_id=clerk_user_id,
            )
            db.add(new_conv)
            db.commit()
            db.refresh(new_conv)
            return new_conv.id

    # Guest Request
    if cleaned_id is not None:
        existing = db.query(Conversation).filter(Conversation.id == cleaned_id).first()
        if existing is not None and existing.user_id is not None:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: You do not have access to this conversation.",
            )
        return cleaned_id

    # If guest does not provide conversation_id, generate an isolated ephemeral UUID
    return str(uuid.uuid4())


def generate_conversation_title(content: str, max_length: int = 50) -> str:
    """
    Generate a clean, deterministic title from the user's first query without calling an LLM.
    Strips leading question phrases, trailing punctuation, capitalizes first character,
    and cleanly truncates at word boundaries.
    """
    if not content:
        return "New conversation"

    cleaned = " ".join(content.strip().split())
    lower = cleaned.lower()
    prefixes = [
        "what is the ",
        "what are the ",
        "tell me about the ",
        "tell me about ",
        "how does the ",
        "what is ",
        "what are ",
        "how to ",
        "how do i ",
        "can you ",
    ]
    for p in prefixes:
        if lower.startswith(p):
            cleaned = cleaned[len(p):].strip()
            break

    cleaned = cleaned.rstrip("?.!,:;")
    if not cleaned:
        return "New conversation"

    # Capitalize first character
    cleaned = cleaned[0].upper() + cleaned[1:]

    # Truncate cleanly if too long
    if len(cleaned) > max_length:
        truncated = cleaned[:max_length].rsplit(" ", 1)[0]
        cleaned = (truncated if len(truncated) > 10 else cleaned[:max_length - 3]).rstrip() + "..."

    return cleaned


def save_user_message(
    db: Session,
    conversation_id: str,
    content: str,
) -> Message:
    """
    Persists a user message to an authenticated conversation.
    If the conversation still has the placeholder title, updates it with a generated title.
    """
    msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=content,
        sources=[],
    )
    db.add(msg)

    # Check and update placeholder conversation title
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation and (not conversation.title or conversation.title in ("New conversation", "New Chat", "New chat", "Untitled")):
        conversation.title = generate_conversation_title(content)

    db.commit()
    db.refresh(msg)
    return msg


def save_assistant_message(
    db: Session,
    conversation_id: str,
    content: str,
    sources: Optional[list] = None,
) -> Message:
    """
    Persists an assistant response to an authenticated conversation.
    """
    msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        sources=sources if sources is not None else [],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_user_conversations(
    db: Session,
    user_id: str,
) -> List[Dict[str, Any]]:
    """
    Retrieves the list of conversations belonging to a verified Clerk user.
    Ordered by created_at descending, with id descending as tiebreaker.
    Excludes any guest conversations (user_id IS NULL) or other users' conversations.
    """
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .all()
    )
    return [
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": _format_utc_iso(conv.created_at),
        }
        for conv in conversations
    ]


def get_conversation_messages(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> List[Dict[str, Any]]:
    """
    Retrieves the chronological list of messages for an authenticated user's conversation.
    Verifies that the conversation exists and belongs to the verified user_id.
    Raises HTTPException(404) if the conversation does not exist.
    Raises HTTPException(403) if the conversation belongs to another user or is unassigned (user_id IS NULL).
    Returns messages ordered by created_at ASC, id ASC.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have access to this conversation.",
        )

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )

    return [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "sources": msg.sources if msg.sources is not None else [],
            "created_at": _format_utc_iso(msg.created_at),
        }
        for msg in messages
    ]


def delete_conversation(
    db: Session,
    conversation_id: str,
    user_id: str,
) -> Dict[str, str]:
    """
    Deletes an authenticated user's conversation and cascades deletion to all messages.
    Raises HTTPException(404) if conversation does not exist.
    Raises HTTPException(403) if conversation belongs to another user or is unassigned.
    """
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have access to this conversation.",
        )

    try:
        db.delete(conversation)
        db.commit()
    except Exception as e:
        db.rollback()
        logfire.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error: unable to delete conversation.",
        )

    return {"message": "Conversation deleted successfully."}


def update_conversation_title(
    db: Session,
    conversation_id: str,
    user_id: str,
    title: str,
) -> Dict[str, Any]:
    """
    Updates the title of an authenticated user's conversation.
    Validates ownership, non-empty title, and maximum length.
    Raises HTTPException(400) if title is empty or exceeds 100 characters.
    Raises HTTPException(404) if conversation does not exist.
    Raises HTTPException(403) if conversation belongs to another user or is unassigned.
    """
    cleaned_title = title.strip() if title and isinstance(title, str) else ""
    if not cleaned_title:
        raise HTTPException(
            status_code=400,
            detail="Title cannot be empty.",
        )
    if len(cleaned_title) > 100:
        raise HTTPException(
            status_code=400,
            detail="Title cannot exceed 100 characters.",
        )

    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    if conversation.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have access to this conversation.",
        )

    try:
        conversation.title = cleaned_title
        db.commit()
        db.refresh(conversation)
    except Exception as e:
        db.rollback()
        logfire.error(f"Failed to update conversation title for {conversation_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database error: unable to update conversation title.",
        )

    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": _format_utc_iso(conversation.created_at),
    }
