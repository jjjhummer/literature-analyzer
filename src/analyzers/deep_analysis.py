"""深度分析模块 v2 - 全方位分析 + 高级可视化"""

import json
import logging
from collections import defaultdict, Counter
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from src.models.paper import Paper, Author, Keyword, Institution, Advisor
from src.analyzers.advanced.text_processor import preprocess_text
from src.storage.paper_repo import PaperRepository

logger = logging.getLogger(__name__)


class DeepAnalyzer:
    """一站式深度分析器"""

    def __init__(self, session: Session):
        self.session = session
        self.repo = PaperRepository(session)
        self._papers_cache = None

    @property
    def papers(self) -> list[Paper]:
        if self._papers_cache is None:
            stmt = select(Paper).order_by(Paper.year.desc())
            self._papers_cache = list(self.session.execute(stmt).scalars().all())
        return self._papers_cache

    # ═══════════════════════════════════════════════════════
    # 1. 概览统计
    # ═══════════════════════════════════════════════════════
    def summary_stats(self) -> dict:
        papers = self.papers
        if not papers:
            return {}
        years = [p.year for p in papers if p.year]
        thesis = sum(1 for p in papers if p.degree_type)
        all_kws = set()
        all_authors = set()
        all_insts = set()
        for p in papers:
            for k in p.keywords:
                all_kws.add(k.keyword)
            for a in p.authors:
                all_authors.add(a.name)
            for inst in p.institutions:
                all_insts.add(inst.name)

        return {
            "total_papers": len(papers),
            "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
            "year_start": min(years) if years else None,
            "year_end": max(years) if years else None,
            "thesis_count": thesis,
            "journal_count": len(papers) - thesis,
            "unique_keywords": len(all_kws),
            "unique_authors": len(all_authors),
            "unique_institutions": len(all_insts),
            "with_fund": sum(1 for p in papers if self._get_fund(p)),
            "with_abstract": sum(1 for p in papers if p.abstract_cn and len(p.abstract_cn) > 20),
        }

    def yearly_growth(self) -> dict:
        """年度增长率分析"""
        yearly = self.repo.get_yearly_counts()
        if not yearly or len(yearly) < 2:
            return {}
        years = sorted(yearly.keys())
        growth = []
        for i in range(1, len(years)):
            prev, curr = yearly[years[i-1]], yearly[years[i]]
            rate = (curr - prev) / prev * 100 if prev > 0 else 0
            growth.append({"年份": years[i], "增长率%": round(rate, 1), "发文量": curr})
        # CAGR
        first, last = yearly[years[0]], yearly[years[-1]]
        n = len(years) - 1
        cagr = ((last / first) ** (1 / n) - 1) * 100 if first > 0 and n > 0 else 0
        return {"growth_data": growth, "cagr": round(cagr, 1)}

    # ═══════════════════════════════════════════════════════
    # 2. 作者分析
    # ═══════════════════════════════════════════════════════
    def author_ranking(self, top_n: int = 20) -> list[dict]:
        counter = Counter()
        author_papers = defaultdict(list)
        for p in self.papers:
            for a in p.authors:
                counter[a.name] += 1
                author_papers[a.name].append(p)
        result = []
        for name, count in counter.most_common(top_n):
            kws = Counter()
            years = set()
            for pp in author_papers[name]:
                for k in pp.keywords:
                    kws[k.keyword] += 1
                if pp.year:
                    years.add(pp.year)
            top_kws = [kw for kw, _ in kws.most_common(5)]
            result.append({
                "name": name, "count": count,
                "top_keywords": top_kws,
                "year_range": f"{min(years)}-{max(years)}" if years else "N/A",
            })
        return result

    def author_productivity_distribution(self) -> dict:
        """作者生产力分布 (Lotka模式)"""
        counter = Counter()
        for p in self.papers:
            for a in p.authors:
                counter[a.name] += 1
        # 统计每个发文量的作者数
        dist = Counter(counter.values())
        return {"labels": sorted(dist.keys()), "counts": [dist[k] for k in sorted(dist.keys())]}

    def author_co_occurrence(self, min_papers: int = 1) -> dict:
        edges = Counter()
        node_weight = Counter()
        for p in self.papers:
            authors = [a.name for a in p.authors]
            for a in authors:
                node_weight[a] += 1
            for i in range(len(authors)):
                for j in range(i + 1, len(authors)):
                    edges[tuple(sorted([authors[i], authors[j]]))] += 1

        nodes_set = set()
        for (a1, a2), w in edges.items():
            if w >= min_papers:
                nodes_set.add(a1)
                nodes_set.add(a2)
        nodes = [{"id": n, "label": n, "weight": node_weight[n]} for n in sorted(nodes_set)]
        edge_list = [{"source": a1, "target": a2, "weight": w}
                     for (a1, a2), w in edges.most_common(100) if w >= min_papers]
        return {"nodes": nodes, "edges": edge_list}

    # ═══════════════════════════════════════════════════════
    # 3. 机构分析
    # ═══════════════════════════════════════════════════════
    def institution_ranking(self, top_n: int = 20) -> list[dict]:
        counter = Counter()
        inst_papers = defaultdict(list)
        for p in self.papers:
            for inst in p.institutions:
                counter[inst.name] += 1
                inst_papers[inst.name].append(p)
        result = []
        for name, count in counter.most_common(top_n):
            kws = Counter()
            degree_cnt = Counter()
            for pp in inst_papers[name]:
                for k in pp.keywords:
                    kws[k.keyword] += 1
                if pp.degree_type:
                    degree_cnt[pp.degree_type] += 1
            top_kws = [kw for kw, _ in kws.most_common(5)]
            result.append({
                "name": name, "count": count,
                "top_keywords": top_kws,
                "doctor_count": degree_cnt.get("博士", 0),
                "master_count": degree_cnt.get("硕士", 0),
            })
        return result

    def institution_keyword_profile(self, top_insts: int = 5, top_kws: int = 10) -> dict:
        """各机构的Top关键词画像（用于雷达图）"""
        counter = Counter()
        inst_papers = defaultdict(list)
        for p in self.papers:
            for inst in p.institutions:
                counter[inst.name] += 1
                inst_papers[inst.name].append(p)

        top = [n for n, _ in counter.most_common(top_insts)]

        # 全局Top关键词
        all_kws = Counter()
        for p in self.papers:
            for k in p.keywords:
                all_kws[k.keyword] += 1
        top_keywords = [kw for kw, _ in all_kws.most_common(top_kws)]

        # 计算每个机构在各关键词上的TF
        profiles = {}
        for inst in top:
            kw_freq = Counter()
            total = 0
            for pp in inst_papers[inst]:
                for k in pp.keywords:
                    kw_freq[k.keyword] += 1
                    total += 1
            profiles[inst] = {kw: round(kw_freq.get(kw, 0) / total * 100, 1) if total > 0 else 0
                              for kw in top_keywords}

        return {"institutions": top, "keywords": top_keywords, "profiles": profiles}

    def institution_yearly(self, top_n: int = 10) -> dict:
        counter = Counter()
        for p in self.papers:
            for inst in p.institutions:
                counter[inst.name] += 1
        top_insts = [name for name, _ in counter.most_common(top_n)]
        result = {}
        for inst in top_insts:
            yearly = Counter()
            for p in self.papers:
                if p.year and any(i.name == inst for i in p.institutions):
                    yearly[p.year] += 1
            result[inst] = dict(sorted(yearly.items()))
        return result

    def institution_collaboration(self, min_weight: int = 1) -> dict:
        """机构合作网络"""
        edges = Counter()
        node_weight = Counter()
        for p in self.papers:
            insts = sorted(set(i.name for i in p.institutions))
            for i in insts:
                node_weight[i] += 1
            for i in range(len(insts)):
                for j in range(i + 1, len(insts)):
                    edges[tuple(sorted([insts[i], insts[j]]))] += 1
        nodes = [{"id": n, "label": n, "weight": w}
                 for n, w in node_weight.most_common(30)]
        nset = {n["id"] for n in nodes}
        edge_list = [{"source": a, "target": b, "weight": w}
                     for (a, b), w in edges.most_common(50)
                     if w >= min_weight and a in nset and b in nset]
        return {"nodes": nodes, "edges": edge_list}

    # ═══════════════════════════════════════════════════════
    # 4. 关键词分析
    # ═══════════════════════════════════════════════════════
    def keyword_burst(self, top_n: int = 15) -> dict:
        """关键词爆发检测：哪些词最近突然变热"""
        yearly_kw = defaultdict(Counter)
        for p in self.papers:
            if p.year:
                for k in p.keywords:
                    yearly_kw[p.year][k.keyword] += 1
        years = sorted(yearly_kw.keys())
        if len(years) < 4:
            return {}

        # 比较最近3年 vs 之前
        recent = years[-3:]
        earlier = years[:-3]
        recent_total = sum(sum(yearly_kw[y].values()) for y in recent)
        earlier_total = sum(sum(yearly_kw[y].values()) for y in earlier)

        if recent_total == 0 or earlier_total == 0:
            return {}

        bursts = []
        all_kws = set()
        for y in yearly_kw.values():
            all_kws.update(y.keys())

        for kw in all_kws:
            recent_cnt = sum(yearly_kw[y].get(kw, 0) for y in recent)
            earlier_cnt = sum(yearly_kw[y].get(kw, 0) for y in earlier)
            recent_rate = recent_cnt / recent_total
            earlier_rate = earlier_cnt / earlier_total if earlier_total > 0 else 0.0001
            if earlier_rate > 0:
                burst_score = recent_rate / earlier_rate
            else:
                burst_score = recent_rate * 100
            if recent_cnt >= 2 and burst_score > 1.2:
                bursts.append({"keyword": kw, "burst_score": round(burst_score, 1),
                               "recent_count": recent_cnt})

        bursts.sort(key=lambda x: x["burst_score"], reverse=True)
        return {"bursts": bursts[:top_n]}

    def keyword_treemap(self, top_n: int = 50) -> list[dict]:
        """关键词矩形树图数据"""
        counter = Counter()
        for p in self.papers:
            for k in p.keywords:
                counter[k.keyword] += 1
        return [{"keyword": kw, "count": cnt} for kw, cnt in counter.most_common(top_n)]

    def keyword_correlation(self, top_n: int = 25) -> dict:
        kw_counter = Counter()
        for p in self.papers:
            for k in p.keywords:
                kw_counter[k.keyword] += 1
        top_kws = [kw for kw, _ in kw_counter.most_common(top_n)]
        paper_kw_map = {}
        for p in self.papers:
            paper_kw_map[p.id] = {k.keyword for k in p.keywords}
        matrix = []
        for kw1 in top_kws:
            row = []
            for kw2 in top_kws:
                both = sum(1 for p_id, kws in paper_kw_map.items() if kw1 in kws and kw2 in kws)
                either = sum(1 for p_id, kws in paper_kw_map.items() if kw1 in kws or kw2 in kws)
                jaccard = both / either if either > 0 else 0
                row.append(round(jaccard, 3))
            matrix.append(row)
        return {"keywords": top_kws, "matrix": matrix}

    def keyword_year_evolution(self, top_n: int = 10) -> dict:
        yearly = defaultdict(Counter)
        for p in self.papers:
            if p.year:
                for k in p.keywords:
                    yearly[p.year][k.keyword] += 1
        years = sorted(yearly.keys())
        if not years:
            return {}
        all_counter = Counter()
        for cnt in yearly.values():
            all_counter.update(cnt)
        top_kws = [kw for kw, _ in all_counter.most_common(top_n)]
        evolution = []
        for year in years:
            row = {"年份": year}
            for kw in top_kws:
                row[kw] = yearly[year].get(kw, 0)
            evolution.append(row)
        return {"keywords": top_kws, "data": evolution}

    # ═══════════════════════════════════════════════════════
    # 5. 基金分析
    # ═══════════════════════════════════════════════════════
    def fund_ranking(self, top_n: int = 15) -> list[dict]:
        counter = Counter()
        fund_papers = defaultdict(list)
        for p in self.papers:
            fund = self._get_fund(p)
            if fund:
                for f in fund.replace(";;", ";").split(";"):
                    f = f.strip()
                    if f:
                        counter[f] += 1
                        fund_papers[f].append(p)
        result = []
        for fund_name, count in counter.most_common(top_n):
            kws = Counter()
            insts = Counter()
            for pp in fund_papers[fund_name][:10]:
                for k in pp.keywords:
                    kws[k.keyword] += 1
                for inst in pp.institutions:
                    insts[inst.name] += 1
            result.append({
                "fund": fund_name[:80], "count": count,
                "top_keywords": [kw for kw, _ in kws.most_common(3)],
                "top_institutions": [inst for inst, _ in insts.most_common(3)],
            })
        return result

    # ═══════════════════════════════════════════════════════
    # 6. 摘要聚类 & LDA
    # ═══════════════════════════════════════════════════════
    def abstract_clustering(self, n_clusters: int = 5, max_docs: int = 300) -> dict:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA

        papers_abs, abstracts = self._get_valid_abstracts()
        if len(abstracts) < 10:
            return {"error": "有摘要的文献不足10篇"}

        # 限制文档数以提速
        if len(abstracts) > max_docs:
            import random
            random.seed(42)
            idx = random.sample(range(len(abstracts)), max_docs)
            papers_abs = [papers_abs[i] for i in idx]
            abstracts = [abstracts[i] for i in idx]

        processed = [" ".join(preprocess_text(a)) for a in abstracts]
        vectorizer = TfidfVectorizer(max_features=500, max_df=0.8, min_df=2)
        X = vectorizer.fit_transform(processed)
        actual_k = max(2, min(n_clusters, len(abstracts) // 5, X.shape[0] - 1))
        kmeans = KMeans(n_clusters=actual_k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        pca = PCA(n_components=2)
        coords = pca.fit_transform(X.toarray())

        feature_names = vectorizer.get_feature_names_out()
        cluster_keywords = {}
        for c in range(actual_k):
            center = kmeans.cluster_centers_[c]
            top_idx = center.argsort()[-10:][::-1]
            cluster_keywords[c] = [feature_names[i] for i in top_idx]

        cluster_papers = defaultdict(list)
        for i, label in enumerate(labels):
            p = papers_abs[i]
            cluster_papers[int(label)].append({
                "id": p.id, "title": (p.title_cn or "")[:60], "year": p.year,
            })

        points = [{"x": float(coords[i][0]), "y": float(coords[i][1]),
                   "cluster": int(labels[i]),
                   "title": (papers_abs[i].title_cn or "")[:40],
                   "year": papers_abs[i].year} for i in range(len(papers_abs))]

        return {
            "clusters": [{"id": k, "keywords": v, "count": len(cluster_papers[k]),
                          "papers": cluster_papers[k][:5]}
                         for k, v in cluster_keywords.items()],
            "points": points, "n_clusters": actual_k,
            "explained_variance": float(sum(pca.explained_variance_ratio_)),
        }

    def lda_topics(self, n_topics: int = 5, max_docs: int = 300) -> dict:
        """LDA主题建模（可视化用）"""
        from gensim import corpora, models

        papers_abs, abstracts = self._get_valid_abstracts()
        if len(abstracts) < 20:
            return {"error": "需要至少20篇有摘要的文献"}

        # 限制文档数以提速
        if len(abstracts) > max_docs:
            import random
            random.seed(42)
            idx = random.sample(range(len(abstracts)), max_docs)
            papers_abs = [papers_abs[i] for i in idx]
            abstracts = [abstracts[i] for i in idx]

        texts = [preprocess_text(a) for a in abstracts]
        texts = [t for t in texts if len(t) >= 5]

        dictionary = corpora.Dictionary(texts)
        dictionary.filter_extremes(no_below=2, no_above=0.8)
        corpus = [dictionary.doc2bow(t) for t in texts]

        k = max(2, min(n_topics, len(texts) // 10))
        lda = models.LdaModel(corpus, id2word=dictionary, num_topics=k,
                              passes=10, random_state=42)

        topics = []
        for i in range(k):
            terms = lda.show_topic(i, topn=10)
            topics.append({"id": i, "terms": [{"word": w, "weight": round(float(wt), 3)}
                                               for w, wt in terms]})

        # 主题-年份关联
        topic_year = defaultdict(lambda: defaultdict(int))
        for idx, bow in enumerate(corpus):
            topic_probs = lda.get_document_topics(bow, minimum_probability=0.1)
            year = papers_abs[idx].year
            if year and topic_probs:
                dominant = max(topic_probs, key=lambda x: x[1])[0]
                topic_year[int(dominant)][year] += 1

        return {"topics": topics, "topic_year": {str(k): dict(v) for k, v in topic_year.items()}}

    # ═══════════════════════════════════════════════════════
    # 7. 时间段对比分析
    # ═══════════════════════════════════════════════════════
    def period_comparison(self, split_year: int = None) -> dict:
        """对比前后两个时间段的研究热点变化"""
        years = sorted([p.year for p in self.papers if p.year])
        if not years or len(years) < 4:
            return {}
        if split_year is None:
            split_year = years[len(years) // 2]

        early_kws = Counter()
        late_kws = Counter()
        for p in self.papers:
            if p.year is None:
                continue
            for k in p.keywords:
                if p.year <= split_year:
                    early_kws[k.keyword] += 1
                else:
                    late_kws[k.keyword] += 1

        # 找出变化最大的关键词
        changes = []
        all_kws = set(list(early_kws.keys()) + list(late_kws.keys()))
        early_total = sum(early_kws.values()) or 1
        late_total = sum(late_kws.values()) or 1

        for kw in all_kws:
            early_rate = early_kws.get(kw, 0) / early_total * 100
            late_rate = late_kws.get(kw, 0) / late_total * 100
            diff = late_rate - early_rate
            if abs(diff) > 0.1:
                changes.append({"keyword": kw, "early_rate": round(early_rate, 2),
                                "late_rate": round(late_rate, 2), "change": round(diff, 2)})

        changes.sort(key=lambda x: abs(x["change"]), reverse=True)
        rising = [c for c in changes if c["change"] > 0][:10]
        declining = [c for c in changes if c["change"] < 0][:10]

        return {
            "split_year": split_year,
            "early_label": f"≤{split_year}",
            "late_label": f">{split_year}",
            "rising": rising,
            "declining": declining,
            "all_changes": changes[:30],
        }

    # ═══════════════════════════════════════════════════════
    # 8. 学位类型分析
    # ═══════════════════════════════════════════════════════
    def degree_analysis(self) -> dict:
        """硕博论文对比分析"""
        doctor_papers = [p for p in self.papers if p.degree_type == "博士"]
        master_papers = [p for p in self.papers if p.degree_type == "硕士"]

        def get_stats(papers_list):
            kws = Counter()
            insts = Counter()
            years = Counter()
            for p in papers_list:
                for k in p.keywords:
                    kws[k.keyword] += 1
                for inst in p.institutions:
                    insts[inst.name] += 1
                if p.year:
                    years[p.year] += 1
            return {"keywords": kws.most_common(10), "institutions": insts.most_common(10),
                    "years": dict(sorted(years.items()))}

        return {
            "doctor": {"count": len(doctor_papers), **get_stats(doctor_papers)},
            "master": {"count": len(master_papers), **get_stats(master_papers)},
        }

    # ═══════════════════════════════════════════════════════
    # Helper
    # ═══════════════════════════════════════════════════════
    def _get_fund(self, paper: Paper) -> str:
        if not paper.extra_data:
            return ""
        try:
            return json.loads(paper.extra_data).get("fund", "")
        except Exception:
            return ""

    def _get_valid_abstracts(self):
        papers_abs, abstracts = [], []
        for p in self.papers:
            a = p.abstract_cn or ""
            if len(a) > 20:
                papers_abs.append(p)
                abstracts.append(a)
        return papers_abs, abstracts
