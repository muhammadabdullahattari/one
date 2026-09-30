from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.persistence.models.security import ApiCredentialModel, ProjectModel
from src.persistence.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[ProjectModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id(self, project_id: UUID) -> ProjectModel | None:
        stmt = select(ProjectModel).where(ProjectModel.project_id == project_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> ProjectModel | None:
        stmt = select(ProjectModel).where(ProjectModel.slug == slug)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_projects(
        self, limit: int = 50, offset: int = 0
    ) -> tuple[list[ProjectModel], int]:
        count_stmt = select(func.count(ProjectModel.project_id))
        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = (
            select(ProjectModel)
            .order_by(ProjectModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all()), total

    async def create_project(
        self, name: str, slug: str, description: str | None = None
    ) -> ProjectModel:
        now = datetime.now(UTC)
        project = ProjectModel(
            project_id=uuid4(),
            name=name,
            slug=slug,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self.session.add(project)
        await self.session.flush()
        return project

    async def delete_project(self, project_id: UUID) -> bool:
        project = await self.get_by_id(project_id)
        if not project:
            return False
        await self.session.delete(project)
        await self.session.flush()
        return True

    async def create_api_key(
        self,
        project_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        role: str,
        scopes: list[str],
    ) -> ApiCredentialModel:
        now = datetime.now(UTC)
        key = ApiCredentialModel(
            principal_id=uuid4(),
            project_id=project_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            role=role,
            scopes=scopes,
            status="active",
            created_at=now,
            last_used_at=None,
        )
        self.session.add(key)
        await self.session.flush()
        return key

    async def list_api_keys(self, project_id: UUID) -> list[ApiCredentialModel]:
        stmt = (
            select(ApiCredentialModel)
            .where(
                ApiCredentialModel.project_id == project_id,
                ApiCredentialModel.status == "active",
            )
            .order_by(ApiCredentialModel.created_at.desc())
        )
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

    async def get_api_key(self, key_id: UUID) -> ApiCredentialModel | None:
        stmt = select(ApiCredentialModel).where(ApiCredentialModel.principal_id == key_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_api_key_by_hash(self, key_hash: str) -> ApiCredentialModel | None:
        stmt = select(ApiCredentialModel).where(
            ApiCredentialModel.key_hash == key_hash,
            ApiCredentialModel.status == "active",
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def revoke_api_key(self, project_id: UUID, key_id: UUID) -> bool:
        stmt = select(ApiCredentialModel).where(
            ApiCredentialModel.principal_id == key_id,
            ApiCredentialModel.project_id == project_id,
        )
        res = await self.session.execute(stmt)
        key = res.scalar_one_or_none()
        if not key:
            return False
        key.status = "revoked"
        await self.session.flush()
        return True
