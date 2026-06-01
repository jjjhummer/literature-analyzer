"""关键词共现网络分析"""

import logging
from collections import defaultdict
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.models.paper import Paper, Keyword
from src.models.paper import paper_keywords
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


class CoOccurrenceAnalyzer(AbstractAnalyzer):
    """关键词共现分析器

    计算关键词在同一篇文献中的共现频率，
    生成共现矩阵和网络图数据。
    """

    name = "co_occurrence"
    description = "关键词共现网络"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        degree_type: Optional[str] = None,
        min_co_occurrence: int = 2,
        top_keywords: int = 50,
        **kwargs,
    ) -> AnalysisResult:
        """分析关键词共现网络

        Args:
            session: 数据库会话
            source: 数据源筛选
            degree_type: 学位类型筛选
            min_co_occurrence: 最小共现次数阈值
            top_keywords: 取高频关键词数量

        Returns:
            共现矩阵和网络边数据
        """
        # 1. 获取所有论文及其关键词
        conditions = []
        if source:
            conditions.append(Paper.source == source)
        if degree_type:
            conditions.append(Paper.degree_type == degree_type)

        stmt = select(Paper).where(and_(*conditions)) if conditions else select(Paper)
        papers = list(session.execute(stmt).scalars().all())

        if not papers:
            return AnalysisResult(
                analysis_type=self.name,
                title="关键词共现网络",
                data={},
                description="暂无数据",
                warnings=["数据库中没有符合条件的文献"],
            )

        # 2. 统计共现
        co_occurrence: dict[tuple[str, str], int] = defaultdict(int)
        keyword_freq: dict[str, int] = defaultdict(int)

        for paper in papers:
            kws = sorted([kw.keyword for kw in paper.keywords])
            # 更新词频
            for kw in kws:
                keyword_freq[kw] += 1
            # 更新共现
            for i in range(len(kws)):
                for j in range(i + 1, len(kws)):
                    pair = (kws[i], kws[j])
                    co_occurrence[pair] += 1

        # 3. 筛选 Top 关键词
        top_kws = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)[:top_keywords]
        top_kw_set = {kw for kw, _ in top_kws}

        # 4. 构建网络数据
        nodes = [{"id": kw, "name": kw, "weight": freq} for kw, freq in top_kws]
        node_ids = {kw: i for i, kw in enumerate([n["id"] for n in nodes])}

        edges = []
        for (kw1, kw2), count in co_occurrence.items():
            if kw1 in top_kw_set and kw2 in top_kw_set and count >= min_co_occurrence:
                # 计算 Jaccard 系数
                union = keyword_freq[kw1] + keyword_freq[kw2] - count
                jaccard = count / union if union > 0 else 0
                edges.append({
                    "source": kw1,
                    "target": kw2,
                    "weight": count,
                    "jaccard": round(jaccard, 4),
                })

        # 5. 共现矩阵
        sorted_kws = sorted(top_kw_set)
        kw_to_idx = {kw: i for i, kw in enumerate(sorted_kws)}
        matrix_size = len(sorted_kws)
        co_matrix = [[0] * matrix_size for _ in range(matrix_size)]

        for (kw1, kw2), count in co_occurrence.items():
            if kw1 in kw_to_idx and kw2 in kw_to_idx:
                i, j = kw_to_idx[kw1], kw_to_idx[kw2]
                co_matrix[i][j] = count
                co_matrix[j][i] = count

        desc = f"分析了 {len(papers)} 篇文献中的 Top {len(nodes)} 个关键词\n"
        desc += f"发现 {len(edges)} 条共现关系 (≥{min_co_occurrence}次)"

        if edges:
            top_edges = sorted(edges, key=lambda x: x["weight"], reverse=True)[:5]
            desc += "\nTop 5 共现对: " + ", ".join([f"{e['source']}-{e['target']}({e['weight']})" for e in top_edges])

        return AnalysisResult(
            analysis_type=self.name,
            title="关键词共现网络",
            data={
                "nodes": nodes,
                "edges": edges,
                "co_occurrence_matrix": co_matrix,
                "keyword_list": sorted_kws,
            },
            description=desc,
        )
