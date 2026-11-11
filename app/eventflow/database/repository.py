from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from eventflow.database.session import Base

ModelT = TypeVar("ModelT", bound=Base)


class GenericRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]):
        self.session = session
        self.model = model

    def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def get(self, obj_id: Any) -> ModelT | None:
        return self.session.get(self.model, obj_id)

    def update(self, obj: ModelT, **fields: Any) -> ModelT:
        for key, value in fields.items():
            setattr(obj, key, value)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def list(self, limit: int = 50) -> list[ModelT]:
        return list(self.session.scalars(select(self.model).limit(limit)))

    def delete(self, obj: ModelT) -> None:
        self.session.delete(obj)
        self.session.commit()
