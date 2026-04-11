"""
Announcements endpoints for the High School Management System API
"""

import hmac
import os

from fastapi import APIRouter, HTTPException, Query, Header
from typing import Dict, Any, Optional, List
from bson import ObjectId
from datetime import date

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _serialize(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _require_teacher(teacher_username: str, authorization: Optional[str]):
    expected_token = os.environ.get("ANNOUNCEMENTS_MANAGEMENT_TOKEN")
    if not expected_token:
        raise HTTPException(status_code=500, detail="Management authentication is not configured")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    provided_token = authorization[len("Bearer "):].strip()
    if not provided_token or not hmac.compare_digest(provided_token, expected_token):
        raise HTTPException(status_code=401, detail="Authentication required")

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")
    return teacher


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements():
    """Return announcements that are currently active (not expired, start date met)."""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": ""},
            {"start_date": {"$lte": today}}
        ]
    }
    return [_serialize(a) for a in announcements_collection.find(query)]


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(
    teacher_username: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """Return all announcements regardless of dates. Requires authentication."""
    _require_teacher(teacher_username, authorization)
    return [_serialize(a) for a in announcements_collection.find()]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """Create a new announcement. Requires authentication."""
    _require_teacher(teacher_username, authorization)

    doc = {
        "message": message,
        "start_date": start_date or None,
        "expiration_date": expiration_date,
        "created_by": teacher_username
    }
    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    teacher_username: str = Query(...),
    start_date: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """Update an existing announcement. Requires authentication."""
    _require_teacher(teacher_username, authorization)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    update_data = {
        "message": message,
        "start_date": start_date or None,
        "expiration_date": expiration_date
    }
    from pymongo import ReturnDocument
    result = announcements_collection.find_one_and_update(
        {"_id": oid},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER
    )
    if not result:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return _serialize(result)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...),
    authorization: Optional[str] = Header(None)
):
    """Delete an announcement. Requires authentication."""
    _require_teacher(teacher_username, authorization)

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
