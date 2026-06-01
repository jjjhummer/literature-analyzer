"""数据库引擎、会话工厂和声明式基类"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from src.config.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


_engine = None
_SessionLocal = None


def get_engine():
    """获取（或创建）数据库引擎"""
    global _engine
    if _engine is None:
        settings = get_settings()
        db_path = settings.database_url.replace("sqlite:///", "")
        _engine = create_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
            pool_pre_ping=True,
        )

        # SQLite 优化
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            if "sqlite" in settings.database_url:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.close()

    return _engine


def get_session():
    """获取一个新的数据库会话"""
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return _SessionLocal()


def init_db():
    """初始化数据库 - 创建所有表"""
    # 确保所有模型已导入（SQLAlchemy 需要导入后才能识别表）
    import src.models.paper  # noqa: F401
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def drop_db():
    """删除所有表（仅用于测试）"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
