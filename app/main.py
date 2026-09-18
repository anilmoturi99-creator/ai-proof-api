from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .database import (
    init_db,
    insert_record,
    verify_record,
    get_record,
    get_all_records,
    update_record,
    delete_record,
)


app = FastAPI(
    title="AI Proof API",
    description="REST API for storing and verifying AI request/response records.",
    version="1.0.0",
)


class RecordCreate(BaseModel):
    request: str = Field(min_length=1)
    response: str = Field(min_length=1)


class RecordUpdate(BaseModel):
    request: str = Field(min_length=1)
    response: str = Field(min_length=1)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "message": "AI Proof API is running",
        "docs": "/docs",
        "health": "/health",
        "records": "/records",
        "verify": "/verify/{record_id}",
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# CREATE
@app.post("/records", status_code=201)
def create_record(payload: RecordCreate):

    created_at = datetime.now(timezone.utc).isoformat()

    record_id, receipt, previous_receipt = insert_record(
        payload.request,
        payload.response,
        created_at
    )

    return {
        "id": record_id,
        "receipt": receipt,
        "previous_receipt": previous_receipt,
        "created_at": created_at,
    }


# READ ALL
@app.get("/records")
def read_all_records():

    records = get_all_records()

    return {
        "count": len(records),
        "records": records,
    }


# READ ONE
@app.get("/records/{record_id}")
def read_record(record_id: int):

    record = get_record(record_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Record not found"
        )

    return dict(record)


# UPDATE
@app.put("/records/{record_id}")
def update_existing_record(
    record_id: int,
    payload: RecordUpdate
):

    updated = update_record(
        record_id,
        payload.request,
        payload.response,
    )

    if not updated:
        raise HTTPException(
            status_code=404,
            detail="Record not found"
        )

    return {
        "message": "Record updated successfully",
        "id": record_id,
    }


# DELETE
@app.delete("/records/{record_id}")
def delete_existing_record(record_id: int):

    deleted = delete_record(record_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Record not found"
        )

    return {
        "message": "Record deleted successfully",
        "id": record_id,
    }


# VERIFY
@app.get("/verify/{record_id}")
def verify(record_id: int):

    result = verify_record(record_id)

    if "record_not_found" in result["broken"]:
        raise HTTPException(
            status_code=404,
            detail=result
        )

    return result