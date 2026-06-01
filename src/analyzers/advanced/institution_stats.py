"""机构分布统计 - 分析文献的机构来源和合作模式"""

import logging
from collections import defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.models.paper import Paper
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class InstitutionStatsAnalyzer(AbstractAnalyzer):
    """机构统计分析器

    分析：
    - 机构发文量排名
    - 机构×年份发文分布
    - 机构研究热点（通过关键词推断）
    - 机构合作网络
    """

    name = "institution_stats"
    description = "机构分布统计"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        degree_type: Optional[str] = None,
        min_papers: int = 2,
        top_n: int = 30,
        **kwargs,
    ) -> AnalysisResult:
        """分析机构分布

        Args:
            session: 数据库会话
            source: 数据源筛选
            degree_type: 学位类型筛选
            min_papers: 最少发文量阈值
            top_n: 排名数量

        Returns:
            机构统计数据
        """
        # 获取有机构信息的论文
        conditions = [Paper.institutions.any()]
        if source:
            conditions.append(Paper.source == source)
        if degree_type:
            conditions.append(Paper.degree_type == degree_type)

        stmt = select(Paper).where(and_(*conditions))
        papers = list(session.execute(stmt).scalars().all())

        if not papers:
            return AnalysisResult(
                analysis_type=self.name,
                title="机构分布统计",
                data={},
                description="暂无数据",
                warnings=["数据库中没有机构信息"],
            )

        # 1. 机构发文量统计
        inst_papers: dict[str, list[Paper]] = defaultdict(list)
        for paper in papers:
            for inst in paper.institutions:
                inst_papers[inst.name].append(paper)

        # 排名
        inst_ranking = sorted(
            [(name, len(ps)) for name, ps in inst_papers.items() if len(ps) >= min_papers],
            key=lambda x: x[1], reverse=True,
        )[:top_n]

        # 2. 机构年度发文分布
        inst_yearly = {}
        for name, _ in inst_ranking[:15]:  # Top 15
            yearly = defaultdict(int)
            for paper in inst_papers[name]:
                if paper.year:
                    yearly[paper.year] += 1
            inst_yearly[name] = dict(sorted(yearly.items()))

        # 3. 机构研究热点
        inst_topics = {}
        for name, _ in inst_ranking[:15]:
            kws = []
            for paper in inst_papers[name]:
                kws.extend([kw.keyword for kw in paper.keywords])
            kw_freq = defaultdict(int)
            for kw in kws:
                kw_freq[kw] += 1
            top_kws = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:10]
            inst_topics[name] = [{"keyword": kw, "count": c} for kw, c in top_kws]

        # 4. 机构合作网络（同一论文中的多机构）
        co_institution: dict[tuple[str, str], int] = defaultdict(int)
        for paper in papers:
            insts = sorted([inst.name for inst in paper.institutions])
            for i in range(len(insts)):
                for j in range(i + 1, len(insts)):
                    pair = (insts[i], insts[j])
                    co_institution[pair] += 1

        # 生成合作边
        collab_edges = [
            {"source": i1, "target": i2, "weight": w}
            for (i1, i2), w in co_institution.items()
            if w >= min_papers
        ]
        collab_edges.sort(key=lambda x: x["weight"], reverse=True)

        desc = f"统计 {len(papers)} 篇文献，{len(inst_papers)} 个机构\n"
        if inst_ranking:
            desc += f"发文最多: {inst_ranking[0][0]} ({inst_ranking[0][1]} 篇)"
        if collab_edges:
            desc += f"\n发现 {len(collab_edges)} 组机构合作关系"

        return AnalysisResult(
            analysis_type=self.name,
            title="机构分布统计",
            data={
                "total_papers": len(papers),
                "total_institutions": len(inst_papers),
                "ranking": [
                    {
                        "name": n, "count": c,
                        "topics": inst_topics.get(n, []),
                        "yearly": inst_yearly.get(n, {}),
                    }
                    for n, c in inst_ranking
                ],
                "collaboration_edges": collab_edges[:100],  # 限制数量
            },
            description=desc,
        )
