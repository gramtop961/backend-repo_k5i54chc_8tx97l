"""
Database Helper Functions

MongoDB helper functions ready to use in your backend code.
Import and use these functions in your API endpoints for database operations.
"""

from pymongo import MongoClient, ReturnDocument
from bson import ObjectId
from datetime import datetime, timezone
import os
from dotenv import load_dotenv
from typing import Union, Optional, Dict, Any
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

_client = None
db = None

database_url = os.getenv("DATABASE_URL")
database_name = os.getenv("DATABASE_NAME")

if database_url and database_name:
    _client = MongoClient(database_url)
    db = _client[database_name]

# Helper: ensure dict

def _to_dict(data: Union[BaseModel, dict]) -> dict:
    if isinstance(data, BaseModel):
        return data.model_dump()
    return data.copy()

# Helper: convert str id to ObjectId

def _oid(id_val: Union[str, ObjectId]) -> ObjectId:
    return id_val if isinstance(id_val, ObjectId) else ObjectId(id_val)

# Helper functions for common database operations

def create_document(collection_name: str, data: Union[BaseModel, dict]) -> str:
    """Insert a single document with timestamp"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")

    data_dict = _to_dict(data)
    now = datetime.now(timezone.utc)
    data_dict['created_at'] = now
    data_dict['updated_at'] = now

    result = db[collection_name].insert_one(data_dict)
    return str(result.inserted_id)


def get_documents(collection_name: str, filter_dict: dict = None, limit: int = None):
    """Get documents from collection"""
    if db is None:
        raise Exception("Database not available. Check DATABASE_URL and DATABASE_NAME environment variables.")
    cursor = db[collection_name].find(filter_dict or {})
    if limit:
        cursor = cursor.limit(limit)
    docs = []
    for d in cursor:
        d['id'] = str(d.pop('_id'))
        docs.append(d)
    return docs


def get_document_by_id(collection_name: str, id_val: Union[str, ObjectId]) -> Optional[Dict[str, Any]]:
    if db is None:
        raise Exception("Database not available.")
    doc = db[collection_name].find_one({"_id": _oid(id_val)})
    if not doc:
        return None
    doc['id'] = str(doc.pop('_id'))
    return doc


def find_one(collection_name: str, filter_dict: dict) -> Optional[Dict[str, Any]]:
    if db is None:
        raise Exception("Database not available.")
    doc = db[collection_name].find_one(filter_dict)
    if not doc:
        return None
    doc['id'] = str(doc.pop('_id'))
    return doc


def update_document(collection_name: str, id_or_filter: Union[str, ObjectId, dict], update_dict: dict) -> Optional[Dict[str, Any]]:
    """Update a document and return the updated version"""
    if db is None:
        raise Exception("Database not available.")
    if isinstance(id_or_filter, dict):
        query = id_or_filter
    else:
        query = {"_id": _oid(id_or_filter)}
    update_dict = {"$set": {**update_dict, "updated_at": datetime.now(timezone.utc)}}
    doc = db[collection_name].find_one_and_update(query, update_dict, return_document=ReturnDocument.AFTER)
    if not doc:
        return None
    doc['id'] = str(doc.pop('_id'))
    return doc


def increment_field(collection_name: str, id_or_filter: Union[str, ObjectId, dict], inc_dict: dict) -> Optional[Dict[str, Any]]:
    if db is None:
        raise Exception("Database not available.")
    if isinstance(id_or_filter, dict):
        query = id_or_filter
    else:
        query = {"_id": _oid(id_or_filter)}
    doc = db[collection_name].find_one_and_update(query, {"$inc": inc_dict, "$set": {"updated_at": datetime.now(timezone.utc)}}, return_document=ReturnDocument.AFTER)
    if not doc:
        return None
    doc['id'] = str(doc.pop('_id'))
    return doc


def delete_document(collection_name: str, id_val: Union[str, ObjectId]) -> bool:
    if db is None:
        raise Exception("Database not available.")
    result = db[collection_name].delete_one({"_id": _oid(id_val)})
    return result.deleted_count == 1
