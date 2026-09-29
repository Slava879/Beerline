from fastapi import APIRouter, Depends
from backend.app.security.deps import CurrentUser, require_roles
from backend.app.users.models import UserRole, User
from backend.app.users.schemas import UserRead
from backend.app.db.session import SessionDep

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUser):
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    user: User = Depends(require_roles(UserRole.DISPATCHER)),
    session: SessionDep = None,
):
    ...