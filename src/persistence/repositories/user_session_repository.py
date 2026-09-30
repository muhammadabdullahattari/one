from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models.security import UserSessionModel
from src.persistence.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSessionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def create_session(
        self,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSessionModel:
        now = datetime.now(UTC)
        user_session = UserSessionModel(
            session_id=uuid4(),
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
        )
        self.session.add(user_session)
        await self.session.flush()
        return user_session

    async def get_active_session_by_token_hash(
        self, refresh_token_hash: str
    ) -> UserSessionModel | None:
        stmt = (
            select(UserSessionModel)
            .where(
                UserSessionModel.refresh_token_hash == refresh_token_hash,
                UserSessionModel.revoked_at.is_(None),
                UserSessionModel.expires_at > datetime.now(UTC),
            )
            .order_by(UserSessionModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return res.scalars().first()

    async def get_session_by_id(self, session_id: UUID) -> UserSessionModel | None:
        stmt = select(UserSessionModel).where(UserSessionModel.session_id == session_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_active_sessions_by_user_id(self, user_id: UUID) -> list[UserSessionModel]:
        stmt = (
            select(UserSessionModel)
            .where(
                UserSessionModel.user_id == user_id,
                UserSessionModel.revoked_at.is_(None),
                UserSessionModel.expires_at > datetime.now(UTC),
            )
            .order_by(UserSessionModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def revoke_session(self, session_id: UUID) -> bool:
        session = await self.get_session_by_id(session_id)
        if not session or session.revoked_at is not None:
            return False
        session.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return True

    async def revoke_user_sessions(self, user_id: UUID) -> int:
        now = datetime.now(UTC)
        stmt = (
            update(UserSessionModel)
            .where(
                UserSessionModel.user_id == user_id,
                UserSessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        res = await self.session.execute(stmt)
        await self.session.flush()
        return int(getattr(res, "rowcount", 0) or 0)
