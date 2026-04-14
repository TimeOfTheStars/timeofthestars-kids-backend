"""Хранение вопросов с сайта."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question_request import QuestionRequest


async def create_question(
    session: AsyncSession,
    *,
    full_name: str,
    phone: str,
) -> QuestionRequest:
    row = QuestionRequest(full_name=full_name, phone=phone)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_questions(
    session: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
) -> list[QuestionRequest]:
    stmt = (
        select(QuestionRequest)
        .order_by(QuestionRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_question(session: AsyncSession, question_id: uuid.UUID) -> bool:
    """Удалить один вопрос по id."""
    stmt = delete(QuestionRequest).where(QuestionRequest.id == question_id)
    result = await session.execute(stmt)
    await session.commit()
    return bool(result.rowcount)


async def delete_all_questions(session: AsyncSession) -> int:
    """Удалить все вопросы и вернуть количество удаленных строк."""
    result = await session.execute(delete(QuestionRequest))
    await session.commit()
    return int(result.rowcount or 0)
