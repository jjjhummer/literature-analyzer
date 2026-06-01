"""通用 CRUD 仓库模式"""

import logging
from typing import Type, TypeVar, Optional, Generic

from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.models.base import Base

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """通用仓库基类"""

    def __init__(self, session: Session, model: Type[T]):
        self.session = session
        self.model = model

    def get_by_id(self, id: int) -> Optional[T]:
        """根据主键获取"""
        return self.session.get(self.model, id)

    def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """获取所有记录"""
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def count_all(self) -> int:
        """统计总数"""
        from sqlalchemy import func
        stmt = select(func.count()).select_from(self.model)
        return self.session.execute(stmt).scalar() or 0

    def add(self, instance: T) -> T:
        """添加一条记录"""
        self.session.add(instance)
        self.session.flush()
        return instance

    def add_all(self, instances: list[T]) -> list[T]:
        """批量添加"""
        self.session.add_all(instances)
        self.session.flush()
        return instances

    def delete(self, instance: T):
        """删除一条记录"""
        self.session.delete(instance)
        self.session.flush()

    def delete_by_id(self, id: int):
        """根据主键删除"""
        stmt = delete(self.model).where(self.model.id == id)
        self.session.execute(stmt)
        self.session.flush()

    def get_or_create(self, defaults: dict = None, **filters) -> tuple[T, bool]:
        """获取或创建记录，返回 (instance, created)"""
        instance = self.session.execute(
            select(self.model).filter_by(**filters)
        ).scalars().first()

        if instance:
            return instance, False

        create_data = {**filters}
        if defaults:
            create_data.update(defaults)
        instance = self.model(**create_data)
        self.session.add(instance)
        self.session.flush()
        return instance, True

    def bulk_insert_or_ignore(self, items: list[dict], unique_field: str):
        """批量插入（如果已存在则忽略）

        Args:
            items: 要插入的数据列表
            unique_field: 用于判重的唯一字段名
        Returns:
            (new_count, skipped_count)
        """
        new_count = 0
        skipped_count = 0

        for item in items:
            existing = self.session.execute(
                select(self.model).filter_by(**{unique_field: item.get(unique_field)})
            ).scalars().first()

            if existing:
                skipped_count += 1
            else:
                instance = self.model(**item)
                self.session.add(instance)
                new_count += 1

        self.session.flush()
        return new_count, skipped_count

    def commit(self):
        """提交事务"""
        self.session.commit()

    def rollback(self):
        """回滚事务"""
        self.session.rollback()
