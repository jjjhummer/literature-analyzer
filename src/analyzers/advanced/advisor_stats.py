"""导师统计 - 分析硕博论文的导师指导情况"""

import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.models.paper import Paper, Advisor
from sqlalchemy import select, and_, func

logger = logging.getLogger(__name__)


class AdvisorStatsAnalyzer(AbstractAnalyzer):
    """导师统计分析器

    针对硕博论文（有导师信息），分析：
    - 导师指导论文数量排名
    - 导师研究主题（通过其学生论文的关键词推断）
    - 导师合作网络（共导关系）
    """

    name = "advisor_stats"
    description = "导师统计分析"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        min_papers: int = 2,
        top_n: int = 20,
        **kwargs,
    ) -> AnalysisResult:
        """分析导师统计

        Args:
            session: 数据库会话
            source: 数据源筛选
            min_papers: 最少指导论文数阈值
            top_n: 排名数量

        Returns:
            导师统计数据
        """
        # 只查询有导师信息的论文
        conditions = [Paper.advisors.any()]
        if source:
            conditions.append(Paper.source == source)

        stmt = select(Paper).where(and_(*conditions))
        papers = list(session.execute(stmt).scalars().all())

        if not papers:
            return AnalysisResult(
                analysis_type=self.name,
                title="导师统计分析",
                data={},
                description="暂无数据",
                warnings=["数据库中没有导师信息（仅硕博论文有此数据）"],
            )

        # 1. 导师指导论文数统计
        advisor_papers: dict[str, list[Paper]] = defaultdict(list)
        for paper in papers:
            for advisor in paper.advisors:
                advisor_papers[advisor.name].append(paper)

        # 排名
        advisor_ranking = sorted(
            [(name, len(ps)) for name, ps in advisor_papers.items() if len(ps) >= min_papers],
            key=lambda x: x[1], reverse=True,
        )[:top_n]

        # 2. 导师研究主题（通过学生论文关键词推断）
        advisor_topics = {}
        for name, _ in advisor_ranking:
            kws = []
            for paper in advisor_papers[name]:
                kws.extend([kw.keyword for kw in paper.keywords])
            kw_freq = defaultdict(int)
            for kw in kws:
                kw_freq[kw] += 1
            top_kws = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            advisor_topics[name] = [{"keyword": kw, "count": c} for kw, c in top_kws]

        # 3. 年度指导分布
        advisor_yearly = {}
        for name, _ in advisor_ranking[:10]:  # Top 10
            yearly = defaultdict(int)
            for paper in advisor_papers[name]:
                if paper.year:
                    yearly[paper.year] += 1
            advisor_yearly[name] = dict(sorted(yearly.items()))

        desc = f"统计 {len(papers)} 篇学位论文，{len(advisor_papers)} 位导师\n"
        if advisor_ranking:
            desc += f"指导最多: {advisor_ranking[0][0]} ({advisor_ranking[0][1]} 篇)"

        return AnalysisResult(
            analysis_type=self.name,
            title="导师统计分析",
            data={
                "total_papers": len(papers),
                "total_advisors": len(advisor_papers),
                "ranking": [{"name": n, "count": c, "topics": advisor_topics.get(n, [])}
                           for n, c in advisor_ranking],
                "yearly_distribution": advisor_yearly,
            },
            description=desc,
        )
