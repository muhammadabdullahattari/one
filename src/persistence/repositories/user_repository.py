from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models.security import UserModel
from src.persistence.repositories.base import BaseRepository
from src.security.password import hash_password


class UserRepository(BaseRepository[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, user_id: UUID) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.user_id == user_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_username(self, username: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.username == username)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_email(self, email: str) -> UserModel | None:
        stmt = select(UserModel).where(UserModel.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_user(
        self, username: str, email: str, password_hash: str, role: str = "operator"
    ) -> UserModel:
        now = datetime.now(UTC)
        user = UserModel(
            user_id=uuid4(),
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def seed_default_users(self) -> None:
        admin = await self.get_by_username("admin")
        if not admin:
            await self.create_user(
                username="admin",
                email="admin@taskengine.internal",
                password_hash=hash_password("adminpassword123"),
                role="admin",
            )
        operator = await self.get_by_username("operator")
        if not operator:
            await self.create_user(
                username="operator",
                email="operator@taskengine.internal",
                password_hash=hash_password("operatorpass123"),
                role="operator",
            )
