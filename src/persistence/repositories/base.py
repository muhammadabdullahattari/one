from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models.base import Base


class BaseRepository[ModelType: Base]:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
