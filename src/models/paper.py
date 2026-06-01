"""核心数据模型：论文、作者、关键词、机构、导师及其关联表"""

import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime,
    ForeignKey, Table, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.models.base import Base


# ═══════════════════════════════════════════════════════════════
# 关联表（多对多）
# ═══════════════════════════════════════════════════════════════

paper_authors = Table(
    "paper_authors",
    Base.metadata,
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("author_id", Integer, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True),
    Column("author_order", Integer, default=1, comment="作者排序: 1=第一作者"),
)

paper_keywords = Table(
    "paper_keywords",
    Base.metadata,
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("keyword_id", Integer, ForeignKey("keywords.id", ondelete="CASCADE"), primary_key=True),
    Column("is_major", Boolean, default=True, comment="是否为主要关键词"),
)

paper_institutions = Table(
    "paper_institutions",
    Base.metadata,
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("institution_id", Integer, ForeignKey("institutions.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(50), default="author", comment="机构角色: author/adviser_institution"),
)

paper_advisors = Table(
    "paper_advisors",
    Base.metadata,
    Column("paper_id", Integer, ForeignKey("papers.id", ondelete="CASCADE"), primary_key=True),
    Column("advisor_id", Integer, ForeignKey("advisors.id", ondelete="CASCADE"), primary_key=True),
)


# ═══════════════════════════════════════════════════════════════
# 实体表
# ═══════════════════════════════════════════════════════════════

class Paper(Base):
    """论文主表"""
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True, comment="数据来源: cnki/wos/scholar")
    source_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, comment="来源数据库内部ID")

    # 标题
    title_cn: Mapped[Optional[str]] = mapped_column(String(1000), comment="中文标题")
    title_en: Mapped[Optional[str]] = mapped_column(String(1000), comment="英文标题")

    # 摘要
    abstract_cn: Mapped[Optional[str]] = mapped_column(Text, comment="中文摘要")
    abstract_en: Mapped[Optional[str]] = mapped_column(Text, comment="英文摘要")

    # 元数据
    doi: Mapped[Optional[str]] = mapped_column(String(200), unique=True, index=True, comment="DOI")
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True, comment="发表年份")
    source_journal: Mapped[Optional[str]] = mapped_column(String(500), comment="期刊名称/学位授予单位")
    degree_type: Mapped[Optional[str]] = mapped_column(String(10), comment="学位类型: 硕士/博士 (仅硕博论文)")
    article_type: Mapped[Optional[str]] = mapped_column(String(50), comment="文献类型: journal/thesis/conference/...")

    # 链接
    url: Mapped[Optional[str]] = mapped_column(String(1000), comment="详情页URL")
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1000), comment="PDF下载URL")
    pdf_path: Mapped[Optional[str]] = mapped_column(String(500), comment="本地PDF路径")

    # 引用
    citation_count: Mapped[Optional[int]] = mapped_column(Integer, default=0, comment="引用次数")

    # 更多元数据（JSON字符串存储灵活字段）
    extra_data: Mapped[Optional[str]] = mapped_column(Text, comment="额外元数据 (JSON)")

    # 时间戳
    crawled_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, comment="爬取时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, comment="更新时间"
    )

    # ── 关联关系 ──
    authors = relationship("Author", secondary=paper_authors, back_populates="papers", lazy="selectin")
    keywords = relationship("Keyword", secondary=paper_keywords, back_populates="papers", lazy="selectin")
    institutions = relationship("Institution", secondary=paper_institutions, back_populates="papers", lazy="selectin")
    advisors = relationship("Advisor", secondary=paper_advisors, back_populates="papers", lazy="selectin")

    # ── 索引 ──
    __table_args__ = (
        Index("ix_papers_source_year", "source", "year"),
        Index("ix_papers_degree_type", "degree_type"),
        Index("ix_papers_article_type", "article_type"),
    )

    def __repr__(self):
        title = (self.title_cn or self.title_en or "")[:50]
        return f"<Paper(id={self.id}, title='{title}...')>"

    def to_dict(self) -> dict:
        """转为字典（包含关联数据）"""
        return {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "title_cn": self.title_cn,
            "title_en": self.title_en,
            "abstract_cn": self.abstract_cn,
            "abstract_en": self.abstract_en,
            "doi": self.doi,
            "year": self.year,
            "source_journal": self.source_journal,
            "degree_type": self.degree_type,
            "article_type": self.article_type,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "pdf_path": self.pdf_path,
            "citation_count": self.citation_count or 0,
            "authors": [a.name for a in self.authors],
            "keywords": [k.keyword for k in self.keywords],
            "institutions": [i.name for i in self.institutions],
            "advisors": [a.name for a in self.advisors],
            "crawled_at": self.crawled_at.isoformat() if self.crawled_at else None,
        }


class Author(Base):
    """作者表"""
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="作者姓名")
    name_normalized: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True, comment="规范化姓名(去空格)"
    )

    papers = relationship("Paper", secondary=paper_authors, back_populates="authors", lazy="selectin")

    def __repr__(self):
        return f"<Author(id={self.id}, name='{self.name}')>"


class Keyword(Base):
    """关键词表"""
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True, comment="中文关键词")
    keyword_en: Mapped[Optional[str]] = mapped_column(String(200), comment="英文关键词")

    papers = relationship("Paper", secondary=paper_keywords, back_populates="keywords", lazy="selectin")

    def __repr__(self):
        return f"<Keyword(id={self.id}, keyword='{self.keyword}')>"


class Institution(Base):
    """机构表"""
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, comment="机构名称")
    name_normalized: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True, index=True, comment="规范化机构名"
    )

    papers = relationship("Paper", secondary=paper_institutions, back_populates="institutions", lazy="selectin")

    def __repr__(self):
        return f"<Institution(id={self.id}, name='{self.name}')>"


class Advisor(Base):
    """导师表（硕博论文特有）"""
    __tablename__ = "advisors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, comment="导师姓名")
    name_normalized: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True, comment="规范化导师名"
    )

    papers = relationship("Paper", secondary=paper_advisors, back_populates="advisors", lazy="selectin")

    def __repr__(self):
        return f"<Advisor(id={self.id}, name='{self.name}')>"
