"""Appointment persistence."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment


async def create_appointment(
    session: AsyncSession,
    *,
    phone: str,
    parent_name: str,
    child_name: str,
    child_age: int,
) -> Appointment:
    """Insert appointment and return persisted entity with generated id."""
    appointment = Appointment(
        phone=phone,
        parent_name=parent_name,
        child_name=child_name,
        child_age=child_age,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


async def list_appointments(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[Appointment]:
    """Список заявок для кабинета: новые сверху."""
    stmt = (
        select(Appointment)
        .order_by(Appointment.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_appointment(session: AsyncSession, appointment_id: uuid.UUID) -> bool:
    """Delete one appointment by id."""
    stmt = delete(Appointment).where(Appointment.id == appointment_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all_appointments(session: AsyncSession) -> int:
    """Delete all appointments and return deleted rows count."""
    result = await session.execute(delete(Appointment))
    await session.commit()
    return int(result.rowcount or 0)
