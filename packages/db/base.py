from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(DeclarativeBase):
    """All models inherit from this. Keeps one metadata instance for Alembic."""
    pass
