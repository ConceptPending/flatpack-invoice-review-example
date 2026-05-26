import bcrypt
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserService:
    @staticmethod
    def _normalize_email(email: str) -> str:
        return email.strip().lower()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        result = await db.execute(
            select(User).where(User.email == UserService._normalize_email(email))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def count_admins(db: AsyncSession) -> int:
        result = await db.execute(
            select(func.count()).select_from(User).where(User.is_admin.is_(True))
        )
        return int(result.scalar_one())

    @staticmethod
    async def create(
        db: AsyncSession,
        email: str,
        password_hash: str,
        is_admin: bool = False,
    ) -> User:
        user = User(
            email=UserService._normalize_email(email),
            password_hash=password_hash,
            is_admin=is_admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
        """Return the user iff the password matches. Returns None for both
        missing user and wrong password — callers MUST NOT distinguish the
        two cases to avoid user enumeration via response codes or messages."""
        user = await UserService.get_by_email(db, email)
        if not user:
            return None
        if not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            return None
        return user
