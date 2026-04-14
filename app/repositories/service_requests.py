"""Persistence for service requests."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service_request import ServiceRequest


async def create_service_request(
    session: AsyncSession,
    *,
    phone: str,
    parent_name: str,
    child_name: str,
    child_age: int,
    service: str,
) -> ServiceRequest:
    row = ServiceRequest(
        phone=phone,
        parent_name=parent_name,
        child_name=child_name,
        child_age=child_age,
        service=service,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_service_requests(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[ServiceRequest]:
    stmt = (
        select(ServiceRequest)
        .order_by(ServiceRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_service_request(session: AsyncSession, service_request_id: uuid.UUID) -> bool:
    """Delete one service request by id."""
    stmt = delete(ServiceRequest).where(ServiceRequest.id == service_request_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all_service_requests(session: AsyncSession) -> int:
    """Delete all service requests and return deleted rows count."""
    result = await session.execute(delete(ServiceRequest))
    await session.commit()
    return int(result.rowcount or 0)
