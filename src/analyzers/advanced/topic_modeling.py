"""LDA 主题建模分析 - 基于论文摘要发现研究主题聚类"""

import json
import logging
from collections import Counter
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

try:
    from gensim import corpora, models
    from gensim.models.coherencemodel import CoherenceModel
    _HAS_GENSIM = True
except ImportError:
    _HAS_GENSIM = False

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.analyzers.advanced.text_processor import preprocess_text, load_stopwords
from src.models.paper import Paper
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class TopicModelingAnalyzer(AbstractAnalyzer):
    """LDA 主题建模分析器

    对论文摘要进行主题建模，自动发现研究方向聚类。
    使用 gensim LDA + 一致性评分选择最优主题数。
    """

    name = "topic_modeling"
    description = "LDA 主题建模"

    def analyze(
        self,
        session: Session,
        num_topics: Optional[int] = None,
        source: Optional[str] = None,
        degree_type: Optional[str] = None,
        min_year: Optional[int] = None,
        passes: int = 10,
        **kwargs,
    ) -> AnalysisResult:
        """执行 LDA 主题建模

        Args:
            session: 数据库会话
            num_topics: 主题数 (None = 自动选择最优值)
            source: 数据源筛选
            degree_type: 学位类型筛选
            min_year: 起始年份
            passes: LDA 训练轮数

        Returns:
            主题建模结果，包含主题-词分布和文档-主题分布
        """
        settings = get_settings()

        if not _HAS_GENSIM:
            return AnalysisResult(
                analysis_type=self.name,
                title="LDA 主题建模",
                data={},
                description="gensim 未安装",
                warnings=["gensim 未安装，无法进行LDA主题建模。请运行: pip install gensim"],
            )

        # 1. 获取论文摘要
        from sqlalchemy import select, and_
        conditions = [Paper.abstract_cn.isnot(None), Paper.abstract_cn != ""]
        if source:
            conditions.append(Paper.source == source)
        if degree_type:
            conditions.append(Paper.degree_type == degree_type)
        if min_year:
            conditions.append(Paper.year >= min_year)

        stmt = select(Paper).where(and_(*conditions))
        papers = list(session.execute(stmt).scalars().all())

        if len(papers) < settings.analysis.min_docs_for_topic_modeling:
            return AnalysisResult(
                analysis_type=self.name,
                title="LDA 主题建模",
                data={},
                description=f"文献数量不足 ({len(papers)} < {settings.analysis.min_docs_for_topic_modeling})",
                warnings=[f"需要至少 {settings.analysis.min_docs_for_topic_modeling} 篇有摘要的文献才能进行主题建模"],
            )

        # 2. 预处理文本
        stopwords = load_stopwords(settings.analysis.extra_stopwords_path or None)
        texts = []
        valid_papers = []

        for paper in papers:
            if paper.abstract_cn:
                tokens = preprocess_text(paper.abstract_cn, stopwords=stopwords)
                if len(tokens) >= 5:  # 最少需要5个有效词
                    texts.append(tokens)
                    valid_papers.append(paper)

        if len(texts) < settings.analysis.min_docs_for_topic_modeling:
            return AnalysisResult(
                analysis_type=self.name,
                title="LDA 主题建模",
                data={},
                description=f"预处理后有效文档不足: {len(texts)}",
                warnings=["预处理后有效文档数量不足"],
            )

        # 3. 构建词典和语料库
        dictionary = corpora.Dictionary(texts)
        # 过滤极端词频
        dictionary.filter_extremes(no_below=2, no_above=0.8)
        corpus = [dictionary.doc2bow(text) for text in texts]

        # 4. 选择最优主题数
        if num_topics is None:
            num_topics = self._select_best_k(
                corpus, dictionary, texts,
                min_k=settings.analysis.min_topics,
                max_k=settings.analysis.max_topics,
            )
            logger.info(f"自动选择主题数: K={num_topics}")

        # 5. 训练 LDA 模型
        lda_model = models.LdaModel(
            corpus=corpus,
            id2word=dictionary,
            num_topics=num_topics,
            passes=passes,
            random_state=42,
            alpha="auto",
            eta="auto",
        )

        # 6. 提取结果
        topics = []
        for topic_id in range(num_topics):
            topic_terms = lda_model.show_topic(topic_id, topn=10)
            topics.append({
                "id": topic_id,
                "terms": [{"word": w, "weight": round(float(weight), 4)} for w, weight in topic_terms],
                "label": f"主题 {topic_id + 1}: {', '.join([w for w, _ in topic_terms[:5]])}",
            })

        # 文档-主题分配
        doc_topics = []
        for i, bow in enumerate(corpus):
            topic_probs = lda_model.get_document_topics(bow, minimum_probability=0.01)
            dominant_topic = max(topic_probs, key=lambda x: x[1]) if topic_probs else (-1, 0)
            paper = valid_papers[i]
            doc_topics.append({
                "paper_id": paper.id,
                "title": (paper.title_cn or paper.title_en or "")[:100],
                "year": paper.year,
                "dominant_topic": int(dominant_topic[0]),
                "dominant_prob": round(float(dominant_topic[1]), 4),
            })

        # 按主题统计文献数
        topic_counts = Counter(d["dominant_topic"] for d in doc_topics)
        for topic in topics:
            topic["doc_count"] = topic_counts.get(topic["id"], 0)

        # 计算一致性分数
        try:
            coherence_model = CoherenceModel(
                model=lda_model, texts=texts, dictionary=dictionary, coherence="c_v"
            )
            coherence_score = round(coherence_model.get_coherence(), 4)
        except Exception:
            coherence_score = None

        desc = f"从 {len(texts)} 篇文献摘要中发现 {num_topics} 个研究主题"
        if coherence_score is not None:
            desc += f"（一致性评分: {coherence_score}）"

        return AnalysisResult(
            analysis_type=self.name,
            title="LDA 主题建模",
            data={
                "num_topics": num_topics,
                "topics": topics,
                "doc_topics": doc_topics,
                "coherence_score": coherence_score,
                "total_docs": len(texts),
                "dictionary_size": len(dictionary),
            },
            description=desc,
        )

    def _select_best_k(self, corpus, dictionary, texts, min_k=3, max_k=15) -> int:
        """使用一致性评分选择最优主题数"""
        best_k = min_k
        best_score = -1

        for k in range(min_k, min(max_k + 1, len(texts) // 5 + 1)):
            try:
                model = models.LdaModel(
                    corpus=corpus, id2word=dictionary, num_topics=k,
                    passes=5, random_state=42,
                )
                coherence = CoherenceModel(
                    model=model, texts=texts, dictionary=dictionary, coherence="c_v"
                )
                score = coherence.get_coherence()

                logger.debug(f"K={k}, coherence={score:.4f}")
                if score > best_score:
                    best_score = score
                    best_k = k
            except Exception as e:
                logger.warning(f"K={k} 评估失败: {e}")
                continue

        return best_k
