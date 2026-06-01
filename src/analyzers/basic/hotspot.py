"""年度研究热点分析"""

import logging
from collections import defaultdict
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.storage.paper_repo import PaperRepository

logger = logging.getLogger(__name__)


class HotspotAnalyzer(AbstractAnalyzer):
    """研究热点分析器

    按年份统计关键词频率，识别各年度热门研究方向。
    支持生成年份×关键词热力图数据。
    """

    name = "hotspot"
    description = "年度研究热点"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        top_n: int = 20,
        min_year: Optional[int] = None,
        max_year: Optional[int] = None,
        **kwargs,
    ) -> AnalysisResult:
        """分析年度研究热点

        Args:
            session: 数据库会话
            source: 数据源筛选
            top_n: 每年返回的热点关键词数
            min_year: 起始年份
            max_year: 结束年份

        Returns:
            {
                "yearly_keywords": {2020: [("关键词1", 15), ...], ...},
                "top_keywords_overall": [("关键词1", 50), ...],
            }
        """
        repo = PaperRepository(session)
        yearly_counts = repo.get_yearly_counts(source=source)

        if not yearly_counts:
            return AnalysisResult(
                analysis_type=self.name,
                title="年度研究热点",
                data={},
                description="暂无数据",
                warnings=["数据库中没有符合条件的文献"],
            )

        years = sorted(yearly_counts.keys())
        if min_year:
            years = [y for y in years if y >= min_year]
        if max_year:
            years = [y for y in years if y <= max_year]

        # 按年统计关键词
        yearly_keywords: dict[int, list[tuple[str, int]]] = {}
        overall_kw_count: dict[str, int] = defaultdict(int)

        for year in years:
            papers = repo.get_papers_by_year(year, source=source)
            kw_count: dict[str, int] = defaultdict(int)

            for paper in papers:
                for kw in paper.keywords:
                    kw_count[kw.keyword] += 1
                    overall_kw_count[kw.keyword] += 1

            # 取 Top N
            top_kws = sorted(kw_count.items(), key=lambda x: x[1], reverse=True)[:top_n]
            yearly_keywords[year] = top_kws

        # 全局 Top 关键词
        top_overall = sorted(overall_kw_count.items(), key=lambda x: x[1], reverse=True)[:top_n]

        # 构建热力图数据 (年份 × 关键词)
        all_top_kws = list(set(kw for kws in yearly_keywords.values() for kw, _ in kws))
        heatmap_data = []
        for year in years:
            kw_dict = dict(yearly_keywords.get(year, []))
            row = {"年份": year}
            row.update({kw: kw_dict.get(kw, 0) for kw in all_top_kws[:20]})
            heatmap_data.append(row)

        desc = f"分析 {len(years)} 年数据，各年 Top {top_n} 热点关键词"
        if top_overall:
            desc += f"\n最热关键词: {', '.join([kw for kw, _ in top_overall[:5]])}"

        return AnalysisResult(
            analysis_type=self.name,
            title="年度研究热点",
            data={
                "yearly_keywords": {
                    str(y): [(kw, cnt) for kw, cnt in kws]
                    for y, kws in yearly_keywords.items()
                },
                "top_keywords_overall": top_overall,
                "heatmap_data": heatmap_data,
            },
            description=desc,
        )
