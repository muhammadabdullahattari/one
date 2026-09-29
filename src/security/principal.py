from dataclasses import dataclass, field

from src.core.constants import ApiAuthMode


@dataclass(frozen=True)
class Principal:
    principal_id: str
    role: str = "operator"
    tenant_id: str | None = None
    scopes: list[str] = field(default_factory=lambda: ["*"])
    auth_mode: ApiAuthMode = ApiAuthMode.JWT
    is_authenticated: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def project_id(self) -> str | None:
        return self.tenant_id

    @property
    def roles(self) -> list[str]:
        return [self.role]

    def has_scope(self, scope: str) -> bool:
        if "*" in self.scopes or "admin" in self.scopes:
            return True
        return scope in self.scopes

    def has_role(self, *roles: str) -> bool:
        if self.role == "admin":
            return True
        return self.role in roles


ANONYMOUS_PRINCIPAL = Principal(
    principal_id="anonymous",
    role="anonymous",
    tenant_id=None,
    scopes=[],
    auth_mode=ApiAuthMode.JWT,
    is_authenticated=False,
)
