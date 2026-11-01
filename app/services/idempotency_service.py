import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.idempotency import IdempotencyKey

def compute_payload_hash(payload: Any) -> str:
    """Computes a deterministic SHA-256 hash of incoming JSON payload."""
    if isinstance(payload, dict):
        serialized = json.dumps(payload, sort_keys=True, default=str)
    else:
        serialized = str(payload)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

async def check_or_lock_idempotency(
    session: AsyncSession,
    client_id: int,
    outlet_id: int,
    key: Optional[str],
    endpoint: str,
    payload: Any
) -> Tuple[Optional[dict], bool]:
    """
    Checks if an idempotency key already exists.
    Returns:
        (saved_response_dict, is_new_execution)
    Raises:
        ValueError if request payload hash does not match original request.
        RuntimeError if previous request with same key is currently 'PROCESSING'.
    """
    if not key or not key.strip():
        return None, True

    current_hash = compute_payload_hash(payload)

    stmt = select(IdempotencyKey).where(
        and_(
            IdempotencyKey.client_id == client_id,
            IdempotencyKey.idempotency_key == key.strip()
        )
    )
    result = await session.execute(stmt)
    record = result.scalars().first()

    if not record:
        # Create a new lock record in PROCESSING state
        new_record = IdempotencyKey(
            client_id=client_id,
            outlet_id=outlet_id,
            idempotency_key=key.strip(),
            endpoint=endpoint,
            request_hash=current_hash,
            status="PROCESSING",
            expires_at=datetime.utcnow() + timedelta(hours=48)
        )
        session.add(new_record)
        await session.flush()
        return None, True

    # Validate payload integrity
    if record.request_hash != current_hash:
        raise ValueError(
            f"Idempotency Key '{key}' was previously used with a different request payload."
        )

    if record.status == "PROCESSING":
        raise RuntimeError(
            f"An identical request with key '{key}' is currently being processed. Please wait."
        )

    # Return cached response
    return record.response_body, False

async def finalize_idempotency(
    session: AsyncSession,
    client_id: int,
    key: Optional[str],
    response_code: int,
    response_body: dict
) -> None:
    """Marks the idempotency record as COMPLETED and stores serialized response."""
    if not key or not key.strip():
        return

    stmt = select(IdempotencyKey).where(
        and_(
            IdempotencyKey.client_id == client_id,
            IdempotencyKey.idempotency_key == key.strip()
        )
    )
    result = await session.execute(stmt)
    record = result.scalars().first()
    if record:
        record.status = "COMPLETED"
        record.response_code = response_code
        record.response_body = response_body
        await session.flush()
