"""年度发文量趋势分析"""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.storage.paper_repo import PaperRepository

logger = logging.getLogger(__name__)


class YearlyTrendAnalyzer(AbstractAnalyzer):
    """年度发文量趋势分析器

    按年份统计文献发表数量，生成趋势数据。
    支持按数据源、文献类型（期刊/硕博）筛选。
    """

    name = "yearly_trend"
    description = "年度发文量趋势"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        degree_type: Optional[str] = None,
        article_type: Optional[str] = None,
        **kwargs,
    ) -> AnalysisResult:
        """分析年度发文量

        Args:
            session: 数据库会话
            source: 数据源筛选 (cnki/wos/scholar)
            degree_type: 学位类型 (硕士/博士)
            article_type: 文献类型 (journal/thesis/conference)

        Returns:
            {'years': [2015, 2016, ...], 'counts': [23, 45, ...]}
        """
        repo = PaperRepository(session)
        yearly_counts = repo.get_yearly_counts(source=source, degree_type=degree_type)

        if not yearly_counts:
            return AnalysisResult(
                analysis_type=self.name,
                title="年度发文量趋势",
                data={"years": [], "counts": []},
                description="暂无数据",
                warnings=["数据库中没有符合条件的文献"],
            )

        # 按年份排序
        sorted_years = sorted(yearly_counts.keys())
        counts = [yearly_counts[y] for y in sorted_years]

        df = pd.DataFrame({"年份": sorted_years, "发文量": counts})

        # 生成描述
        total = sum(counts)
        peak_year = sorted_years[counts.index(max(counts))]
        desc = f"共 {total} 篇文献，峰值出现在 {peak_year} 年 ({max(counts)} 篇)"

        return AnalysisResult(
            analysis_type=self.name,
            title="年度发文量趋势",
            data={"years": sorted_years, "counts": counts, "total": total},
            chart_data=df,
            description=desc,
        )
