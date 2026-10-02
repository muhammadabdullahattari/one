from collections.abc import Callable

from fastapi import HTTPException, status

from src.security.principal import Principal

ALLOWED_ROLES = {"admin", "developer", "viewer", "worker"}


def check_project_access(principal: Principal, target_project_id: str | None) -> bool:
    if not target_project_id:
        return False
    if principal.is_admin and (principal.project_id is None or principal.project_id == "*"):
        return True
    if not principal.project_id:
        return False
    return str(principal.project_id) == str(target_project_id)


check_tenant_access = check_project_access


def enforce_project_access(principal: Principal, target_project_id: str | None) -> None:
    if not check_project_access(principal, target_project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": f"Cross-tenant access forbidden: principal does not have access to tenant '{target_project_id}'",
                }
            },
        )


enforce_tenant_access = enforce_project_access


def enforce_role(principal: Principal, allowed_roles: tuple[str, ...]) -> None:
    if not any(principal.has_role(r) for r in allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "INSUFFICIENT_PERMISSIONS",
                    "message": f"Operation requires one of roles: {list(allowed_roles)}; principal has roles: {principal.roles}",
                }
            },
        )


def require_role(
    *roles: str,
) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal) -> Principal:
        enforce_role(principal, roles)
        return principal

    return dependency
