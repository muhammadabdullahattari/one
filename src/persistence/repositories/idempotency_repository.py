from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.domain.entities import IdempotencyKey
from src.persistence.models.idempotency import IdempotencyKeyModel
from src.persistence.repositories.base import BaseRepository


class IdempotencyRepository(BaseRepository[IdempotencyKeyModel]):
    async def get_key(self, scope: str, idempotency_key: str) -> IdempotencyKey | None:
        now = datetime.now(UTC)
        stmt = select(IdempotencyKeyModel).where(
            IdempotencyKeyModel.scope == scope,
            IdempotencyKeyModel.idempotency_key == idempotency_key,
            IdempotencyKeyModel.expires_at > now,
        )
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return IdempotencyKey(
            scope=m.scope,
            idempotency_key=m.idempotency_key,
            task_id=m.task_id,
            request_hash=m.request_hash,
            created_at=m.created_at,
            expires_at=m.expires_at,
        )

    async def record_key(self, idempotency: IdempotencyKey) -> bool:
        stmt = (
            insert(IdempotencyKeyModel)
            .values(
                scope=idempotency.scope,
                idempotency_key=idempotency.idempotency_key,
                task_id=idempotency.task_id,
                request_hash=idempotency.request_hash,
                created_at=idempotency.created_at,
                expires_at=idempotency.expires_at,
            )
            .on_conflict_do_nothing(index_elements=["scope", "idempotency_key"])
            .returning(IdempotencyKeyModel.idempotency_key)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none() is not None
