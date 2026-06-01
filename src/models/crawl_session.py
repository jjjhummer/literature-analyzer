"""爬取会话模型 - 记录每次爬取的元信息"""

import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class CrawlSession(Base):
    """爬取会话记录"""
    __tablename__ = "crawl_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="数据源")
    keyword: Mapped[str] = mapped_column(String(500), nullable=False, index=True, comment="搜索关键字")

    started_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, comment="开始时间"
    )
    finished_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment="结束时间")

    papers_found: Mapped[int] = mapped_column(Integer, default=0, comment="找到的论文数")
    papers_new: Mapped[int] = mapped_column(Integer, default=0, comment="新增论文数")
    papers_skipped: Mapped[int] = mapped_column(Integer, default=0, comment="跳过的论文数（已存在）")

    status: Mapped[str] = mapped_column(
        String(20), default="running", index=True, comment="状态: running/completed/failed/cancelled"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, comment="错误信息")

    # 额外信息
    extra_params: Mapped[Optional[str]] = mapped_column(Text, comment="额外参数 (JSON)")

    def __repr__(self):
        return f"<CrawlSession(id={self.id}, source='{self.source}', keyword='{self.keyword}', status='{self.status}')>"

    def mark_completed(self, found: int, new: int, skipped: int):
        """标记会话完成"""
        self.status = "completed"
        self.finished_at = datetime.datetime.utcnow()
        self.papers_found = found
        self.papers_new = new
        self.papers_skipped = skipped

    def mark_failed(self, error: str):
        """标记会话失败"""
        self.status = "failed"
        self.finished_at = datetime.datetime.utcnow()
        self.error_message = error

    def mark_cancelled(self):
        """标记会话取消"""
        self.status = "cancelled"
        self.finished_at = datetime.datetime.utcnow()


class AnalysisCache(Base):
    """分析结果缓存"""
    __tablename__ = "analysis_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="分析类型")
    parameters: Mapped[str] = mapped_column(Text, nullable=False, comment="分析参数 (JSON)")
    result_json: Mapped[Optional[str]] = mapped_column(Text, comment="分析结果 (JSON)")
    paper_count: Mapped[int] = mapped_column(Integer, default=0, comment="分析时的论文数量")

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, comment="创建时间"
    )

    class Meta:
        indexes = [
            ("ix_analysis_cache_type_params", "analysis_type", "parameters"),
        ]

    def __repr__(self):
        return f"<AnalysisCache(id={self.id}, type='{self.analysis_type}')>"
