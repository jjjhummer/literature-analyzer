"""Paper 专用仓库 - 包含去重、搜索等专用查询"""

import logging
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, joinedload

from src.models.paper import Paper, Author, Keyword, Institution, Advisor
from src.storage.repository import BaseRepository

logger = logging.getLogger(__name__)


class PaperRepository(BaseRepository[Paper]):
    """Paper 专用仓库"""

    def __init__(self, session: Session):
        super().__init__(session, Paper)

    def find_by_doi(self, doi: str) -> Optional[Paper]:
        """根据 DOI 查找论文"""
        if not doi:
            return None
        stmt = select(Paper).where(Paper.doi == doi)
        return self.session.execute(stmt).scalars().first()

    def find_by_source_id(self, source: str, source_id: str) -> Optional[Paper]:
        """根据来源ID查找论文"""
        if not source_id:
            return None
        stmt = select(Paper).where(
            and_(Paper.source == source, Paper.source_id == source_id)
        )
        return self.session.execute(stmt).scalars().first()

    def find_by_title_fuzzy(self, title: str, threshold: float = 0.85) -> Optional[Paper]:
        """模糊标题匹配（用于跨源去重）"""
        if not title:
            return None

        # 先找到所有标题
        stmt = select(Paper).where(
            or_(Paper.title_cn.isnot(None), Paper.title_en.isnot(None))
        )
        papers = self.session.execute(stmt).scalars().all()

        title_lower = title.lower().strip()
        for paper in papers:
            for paper_title in [paper.title_cn, paper.title_en]:
                if not paper_title:
                    continue
                similarity = SequenceMatcher(None, title_lower, paper_title.lower().strip()).ratio()
                if similarity >= threshold:
                    return paper

        return None

    def is_duplicate(self, source: str, source_id: str = None, doi: str = None,
                     title: str = None) -> Optional[Paper]:
        """综合去重检查

        按优先级检查: 1) DOI精确匹配 2) 来源ID匹配 3) 标题模糊匹配
        """
        # 1. DOI
        if doi:
            paper = self.find_by_doi(doi)
            if paper:
                return paper

        # 2. 来源ID
        if source and source_id:
            paper = self.find_by_source_id(source, source_id)
            if paper:
                return paper

        # 3. 标题模糊匹配
        if title:
            paper = self.find_by_title_fuzzy(title)
            if paper:
                return paper

        return None

    def search_by_keyword(self, keyword: str, source: str = None,
                          year_from: int = None, year_to: int = None,
                          degree_type: str = None) -> list[Paper]:
        """按条件搜索论文"""
        conditions = []

        if source:
            conditions.append(Paper.source == source)
        if year_from is not None:
            conditions.append(Paper.year >= year_from)
        if year_to is not None:
            conditions.append(Paper.year <= year_to)
        if degree_type:
            conditions.append(Paper.degree_type == degree_type)

        # 关键字搜索（标题或摘要）
        if keyword:
            keyword_cond = or_(
                Paper.title_cn.contains(keyword),
                Paper.title_en.contains(keyword),
                Paper.abstract_cn.contains(keyword),
                Paper.abstract_en.contains(keyword),
            )
            conditions.append(keyword_cond)

        stmt = select(Paper).where(and_(*conditions)).order_by(Paper.year.desc())
        return list(self.session.execute(stmt).scalars().all())

    def get_yearly_counts(self, source: str = None, degree_type: str = None) -> dict[int, int]:
        """获取年度发文量统计"""
        conditions = [Paper.year.isnot(None)]
        if source:
            conditions.append(Paper.source == source)
        if degree_type:
            conditions.append(Paper.degree_type == degree_type)

        stmt = (
            select(Paper.year, func.count(Paper.id))
            .where(and_(*conditions))
            .group_by(Paper.year)
            .order_by(Paper.year)
        )
        results = self.session.execute(stmt).all()
        return {year: count for year, count in results if year}

    def get_papers_by_year(self, year: int, source: str = None) -> list[Paper]:
        """获取指定年份的所有论文"""
        conditions = [Paper.year == year]
        if source:
            conditions.append(Paper.source == source)

        stmt = select(Paper).where(and_(*conditions))
        return list(self.session.execute(stmt).scalars().all())

    def get_all_keywords_count(self, source: str = None, limit: int = 100) -> list[tuple[str, int]]:
        """获取关键词频率统计"""
        from src.models.paper import paper_keywords
        from src.models.paper import Keyword

        stmt = (
            select(Keyword.keyword, func.count(paper_keywords.c.paper_id).label("cnt"))
            .join(paper_keywords, Keyword.id == paper_keywords.c.keyword_id)
            .join(Paper, Paper.id == paper_keywords.c.paper_id)
        )

        if source:
            stmt = stmt.where(Paper.source == source)

        stmt = stmt.group_by(Keyword.id).order_by(func.count(paper_keywords.c.paper_id).desc()).limit(limit)
        results = self.session.execute(stmt).all()
        return [(kw, cnt) for kw, cnt in results]


class AuthorRepository(BaseRepository[Author]):
    """Author 专用仓库"""

    def __init__(self, session: Session):
        super().__init__(session, Author)

    def get_or_create_by_name(self, name: str) -> tuple[Author, bool]:
        """根据姓名获取或创建作者"""
        normalized = name.strip().lower()
        return self.get_or_create(
            defaults={"name": name.strip()},
            name_normalized=normalized,
        )


class KeywordRepository(BaseRepository[Keyword]):
    """Keyword 专用仓库"""

    def __init__(self, session: Session):
        super().__init__(session, Keyword)

    def get_or_create_by_keyword(self, keyword: str, keyword_en: str = None) -> tuple[Keyword, bool]:
        """根据关键词获取或创建"""
        return self.get_or_create(
            defaults={"keyword_en": keyword_en},
            keyword=keyword.strip(),
        )


class InstitutionRepository(BaseRepository[Institution]):
    """Institution 专用仓库"""

    def __init__(self, session: Session):
        super().__init__(session, Institution)

    def get_or_create_by_name(self, name: str) -> tuple[Institution, bool]:
        """根据机构名获取或创建"""
        normalized = name.strip().lower()
        return self.get_or_create(
            defaults={"name": name.strip()},
            name_normalized=normalized,
        )


class AdvisorRepository(BaseRepository[Advisor]):
    """Advisor 专用仓库"""

    def __init__(self, session: Session):
        super().__init__(session, Advisor)

    def get_or_create_by_name(self, name: str) -> tuple[Advisor, bool]:
        """根据导师名获取或创建"""
        normalized = name.strip().lower()
        return self.get_or_create(
            defaults={"name": name.strip()},
            name_normalized=normalized,
        )
