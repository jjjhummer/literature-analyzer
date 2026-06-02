"""文献分析系统 - 单页滚动版"""

import sys, io, base64, os, asyncio, importlib
from pathlib import Path
from datetime import datetime
from collections import Counter

# ⚠️ 必须在任何 matplotlib 导入前设置后端（Linux headless 兼容）
import matplotlib
try:
    matplotlib.use("Agg")
except Exception:
    pass

_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

importlib.invalidate_caches()
for _mod in list(sys.modules.keys()):
    if _mod.startswith("src."):
        del sys.modules[_mod]

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import networkx as nx

from src.config.settings import get_settings
from src.models.base import init_db, get_session, get_engine
from src.storage.paper_repo import PaperRepository
from src.import_cnki import parse_file, import_to_db
from src.analyzers.deep_analysis import DeepAnalyzer
from src.analyzers.basic.yearly_trend import YearlyTrendAnalyzer
from src.analyzers.basic.hotspot import HotspotAnalyzer
from src.analyzers.basic.keyword_cloud import KeywordCloudAnalyzer

# ── Init ──
st.set_page_config(page_title="文献分析系统", page_icon="📚", layout="wide")
settings = get_settings()
settings.ensure_directories()
try:
    init_db()
except Exception:
    pass

# ── CSS ──
st.markdown("""<style>
.card{background:#f5f7fa;border-radius:10px;padding:15px;margin:5px 0;border:1px solid #e0e4e8;}
.metric{text-align:center;background:#f0f4ff;border-radius:10px;padding:12px 5px;}
.metric .n{font-size:2em;font-weight:bold;color:#1a73e8;}
.metric .l{font-size:0.75em;color:#666;}
.section-title{font-size:1.3em;font-weight:bold;margin-top:20px;padding:10px 0;border-bottom:2px solid #1a73e8;}
</style>""", unsafe_allow_html=True)

# ── Session State ──
for key, default in [("analyzer", None), ("analyzer_version", 0),
                       ("file_processed", False), ("total_papers", 0),
                       ("_last_upload_name", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

_ANALYZER_CACHE_VERSION = 5


def get_analyzer():
    ver = st.session_state.get("analyzer_version", 0)
    if ver != _ANALYZER_CACHE_VERSION or st.session_state.get("analyzer") is None:
        old = st.session_state.get("analyzer")
        if old is not None and hasattr(old, "session"):
            try: old.session.close()
            except Exception: pass
        s = get_session()
        st.session_state.analyzer = DeepAnalyzer(s)
        st.session_state.analyzer_version = _ANALYZER_CACHE_VERSION
    return st.session_state.analyzer


# ═══════════════════ Header ═══════════════════
st.markdown("## 📚 文献深度分析系统")

# ── 总文献数 ──
try:
    s = get_session()
    st.session_state.total_papers = PaperRepository(s).count_all()
    s.close()
except Exception:
    st.session_state.total_papers = 0
total = st.session_state.total_papers

# ── 上传区 ──
if total == 0:
    st.info("👋 请上传知网导出文件开始分析。在知网搜索 → 勾选文献 → 导出 → TXT格式 → 上传到这里")

c1, c2, c3 = st.columns([3, 1, 1])
with c1:
    uploaded = st.file_uploader(
        "上传知网导出文件 (TXT/Excel)", type=["txt", "xls", "xlsx"], key="up",
        label_visibility="collapsed" if total > 0 else "visible",
        help="知网搜索→勾选文献→导出→TXT格式→上传"
    )
with c2:
    if total > 0:
        st.caption(f"📦 已导入 {total} 篇")
with c3:
    if total > 0:
        if st.button("🗑 清空数据", type="secondary", use_container_width=True):
            try:
                old = st.session_state.get("analyzer")
                if old is not None and hasattr(old, "session"):
                    try: old.session.close()
                    except Exception: pass
                engine = get_engine()
                engine.dispose()
                for k in ["analyzer", "analyzer_version", "total_papers",
                          "file_processed", "_last_upload_name", "sel"]:
                    if k in st.session_state:
                        st.session_state[k] = None if k == "analyzer" else (0 if k in ("analyzer_version", "total_papers") else (False if k == "file_processed" else ""))
                st.session_state.analyzer_version = 0
                st.session_state.total_papers = 0
                st.session_state.file_processed = False
                st.session_state._last_upload_name = ""
                from src.models.base import Base
                import src.models.paper
                engine2 = get_engine()
                Base.metadata.drop_all(bind=engine2)
                Base.metadata.create_all(bind=engine2)
                st.success("数据已清除")
                st.rerun()
            except Exception as e:
                st.error(f"清除失败: {e}")

# ── 导入处理 ──
if uploaded is not None:
    if uploaded.name == st.session_state._last_upload_name:
        pass
    else:
        import tempfile
        tmp_dir = Path(tempfile.gettempdir()) / "literature_analyzer"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp = tmp_dir / f"up_{datetime.now().strftime('%H%M%S')}{Path(uploaded.name).suffix}"
        file_bytes = uploaded.read()
        with open(tmp, "wb") as f:
            f.write(file_bytes)
        try:
            records = parse_file(str(tmp))
            if records:
                s = get_session()
                new, skip = import_to_db(records, s)
                s.close()
                st.success(f"✅ 导入完成: 新增 {new} 篇, 跳过 {skip} 篇重复")
                st.session_state.analyzer = None
                st.session_state.analyzer_version = 0
                st.session_state.total_papers = new
                st.session_state._last_upload_name = uploaded.name
                st.rerun()
            else:
                st.warning("未解析到文献记录，请检查文件格式")
        except Exception as e:
            st.error(f"解析失败: {e}")

# 刷新 total
try:
    s = get_session()
    total = PaperRepository(s).count_all()
    s.close()
except Exception:
    total = 0

if total == 0:
    st.markdown("---")
    st.markdown("""
    ### 📖 使用说明
    1. 打开 [知网](https://kns.cnki.net) 搜索你感兴趣的主题
    2. 勾选需要的文献 → 点击 **导出与分析** → 选择 **TXT格式**
    3. 将导出的 `.txt` 文件上传到本系统
    4. 系统自动解析并展示分析结果
    """)
    st.stop()

# ═══════════════════ 加载分析器 ═══════════════════
try:
    analyzer = get_analyzer()
except Exception as e:
    st.error(f"初始化分析失败: {e}")
    st.stop()

stats = analyzer.summary_stats()
gr = analyzer.yearly_growth()

# ═══════════════════ KPI Cards ═══════════════════
st.markdown('<div class="section-title">📊 数据概览</div>', unsafe_allow_html=True)
kpi_cols = st.columns(8)
kpis = [
    ("总文献", stats.get("total_papers", 0)),
    ("年份范围", stats.get("year_range", "N/A")),
    ("博士论文", stats.get("thesis_count", 0)),
    ("期刊", stats.get("journal_count", 0)),
    ("作者", stats.get("unique_authors", 0)),
    ("机构", stats.get("unique_institutions", 0)),
    ("关键词", stats.get("unique_keywords", 0)),
    ("CAGR", f"{gr.get('cagr', 0)}%"),
]
for col, (label, val) in zip(kpi_cols, kpis):
    with col:
        st.markdown(f"""<div class="metric"><div class="n">{val}</div><div class="l">{label}</div></div>""",
                    unsafe_allow_html=True)

# ═══════════════════ 1. 发文趋势 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">📈 发文趋势与增长</div>', unsafe_allow_html=True)

c1, c2 = st.columns([2, 1])
with c1:
    yearly = analyzer.repo.get_yearly_counts()
    if yearly:
        df = pd.DataFrame({"年份": sorted(yearly.keys()),
                           "发文量": [yearly[y] for y in sorted(yearly.keys())]})
        fig = px.bar(df, x="年份", y="发文量")
        fig.add_trace(go.Scatter(x=df["年份"], y=df["发文量"], mode="lines+markers",
                                 line=dict(width=3, color="#e74c3c"), name="趋势"))
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

with c2:
    if gr.get("growth_data"):
        gdf = pd.DataFrame(gr["growth_data"])
        fig = px.bar(gdf, x="年份", y="增长率%", color="增长率%",
                     color_continuous_scale=["green", "yellow", "red"],
                     color_continuous_midpoint=0,
                     title=f"年增长率 (CAGR: {gr['cagr']}%)")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

# 时间段对比
period = analyzer.period_comparison()
if period and period.get("rising"):
    st.markdown("#### 📊 时间段对比")
    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown(f"**📈 上升趋势 ({period['late_label']})**")
        for c in period["rising"][:8]:
            st.markdown(f"- {c['keyword']}: {c['early_rate']:.1f}% → {c['late_rate']:.1f}% (+{c['change']:.1f})")
    with pc2:
        st.markdown(f"**📉 下降趋势 ({period['late_label']})**")
        for c in period["declining"][:8]:
            st.markdown(f"- {c['keyword']}: {c['early_rate']:.1f}% → {c['late_rate']:.1f}% ({c['change']:.1f})")

# 突现关键词
burst = analyzer.keyword_burst(top_n=10)
if burst.get("bursts"):
    st.markdown("#### 🔥 近年突现关键词")
    bcols = st.columns(5)
    for i, b in enumerate(burst["bursts"][:5]):
        with bcols[i]:
            st.metric(label=b['keyword'], value=f"×{b['burst_score']}", delta=f"{b['recent_count']}篇")

# ═══════════════════ 2. 关键词分析 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">🔗 关键词分析</div>', unsafe_allow_html=True)

# 相关性热力图 + 树图
kr1, kr2 = st.columns([3, 2])
with kr1:
    corr = analyzer.keyword_correlation(top_n=15)
    if corr.get("matrix"):
        cdf = pd.DataFrame(corr["matrix"], index=corr["keywords"], columns=corr["keywords"])
        fig = px.imshow(cdf, aspect="auto", color_continuous_scale="RdBu_r",
                        title="关键词相关性热力图 (Jaccard)", zmin=0, zmax=1)
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

with kr2:
    treemap = analyzer.keyword_treemap(top_n=30)
    if treemap:
        tdf = pd.DataFrame(treemap)
        fig = px.treemap(tdf, path=["keyword"], values="count",
                         title="关键词分布树图", color="count", color_continuous_scale="Blues")
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

# 词云 + 演变热力图
wc1, wc2 = st.columns([1, 2])
with wc1:
    try:
        session = get_session()
        kw_analyzer = KeywordCloudAnalyzer()
        result = kw_analyzer.analyze(session, max_words=150)
        session.close()
        if result.data.get("image_base64"):
            st.markdown(f'<img src="data:image/png;base64,{result.data["image_base64"]}" '
                        f'style="max-width:100%;border-radius:8px;">', unsafe_allow_html=True)
        elif result.warnings:
            for w in result.warnings:
                st.warning(w)
    except Exception as e:
        st.warning(f"词云生成失败: {e}")

with wc2:
    evo = analyzer.keyword_year_evolution(top_n=8)
    if evo and evo.get("data"):
        evo_df = pd.DataFrame(evo["data"]).set_index("年份")
        fig = px.imshow(evo_df.T, aspect="auto", color_continuous_scale="YlOrRd",
                        title="关键词×年份 演变热力图")
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

# ═══════════════════ 3. 作者分析 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">👤 作者分析</div>', unsafe_allow_html=True)

ar1, ar2 = st.columns(2)
with ar1:
    author_rank = analyzer.author_ranking(top_n=15)
    if author_rank:
        adf = pd.DataFrame([{"作者": a["name"], "发文量": a["count"]} for a in author_rank])
        fig = px.bar(adf, x="发文量", y="作者", orientation="h", color="发文量",
                     color_continuous_scale="Blues", title="作者发文排名")
        fig.update_layout(yaxis=dict(autorange="reversed"), height=380)
        st.plotly_chart(fig, use_container_width=True)

with ar2:
    prod = analyzer.author_productivity_distribution()
    if prod.get("labels"):
        pdf = pd.DataFrame({"发文量": prod["labels"], "作者数": prod["counts"]})
        fig = px.bar(pdf, x="发文量", y="作者数", title="作者生产力分布")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

# 作者合作网络 - 独占一行，全宽展示
coauthor = analyzer.author_co_occurrence(min_papers=1)
if coauthor["edges"]:
    st.markdown("#### 🤝 作者合作网络")
    G = nx.Graph()
    for n in coauthor["nodes"]:
        G.add_node(n["id"])
    for e in coauthor["edges"][:60]:
        G.add_edge(e["source"], e["target"], weight=e["weight"])
    pos = nx.spring_layout(G, k=1.5, iterations=50, seed=42)
    edge_x, edge_y = [], []
    for u, v in G.edges():
        x0, y0 = pos[u]; x1, y1 = pos[v]
        edge_x.extend([x0, x1, None]); edge_y.extend([y0, y1, None])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, mode="lines",
                             line=dict(width=0.4, color="#ccc"), hoverinfo="none"))
    deg = dict(G.degree())
    fig.add_trace(go.Scatter(
        x=[pos[n][0] for n in G.nodes()], y=[pos[n][1] for n in G.nodes()],
        mode="markers+text", text=[n for n in G.nodes()],
        textposition="top center", textfont=dict(size=10),
        marker=dict(size=[max(8, deg.get(n, 1) * 4) for n in G.nodes()],
                    color=list(deg.values()), colorscale="Viridis",
                    showscale=True, colorbar=dict(title="度")),
    ))
    fig.update_layout(title="作者合作网络", height=700, showlegend=False,
                      xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                      yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════ 4. 机构分析 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">🏛 机构分析</div>', unsafe_allow_html=True)

ir1, ir2 = st.columns(2)
with ir1:
    inst_rank = analyzer.institution_ranking(top_n=15)
    if inst_rank:
        idf = pd.DataFrame([{"机构": r["name"], "发文量": r["count"]} for r in inst_rank])
        fig = px.bar(idf, x="发文量", y="机构", orientation="h", color="发文量",
                     color_continuous_scale="Greens", title="机构发文排名")
        fig.update_layout(yaxis=dict(autorange="reversed"), height=400)
        st.plotly_chart(fig, use_container_width=True)

with ir2:
    profile = analyzer.institution_keyword_profile(top_insts=4, top_kws=8)
    if profile.get("institutions"):
        fig = go.Figure()
        for inst in profile["institutions"]:
            fig.add_trace(go.Scatterpolar(
                r=[profile["profiles"][inst].get(kw, 0) for kw in profile["keywords"]],
                theta=profile["keywords"], fill="toself", name=inst[:15],
            ))
        max_v = max(max(profile["profiles"][inst].values()) for inst in profile["institutions"])
        fig.update_layout(title="机构关键词画像", height=400,
                          polar=dict(radialaxis=dict(visible=True, range=[0, max_v * 1.2])))
        st.plotly_chart(fig, use_container_width=True)

# 机构合作网络
icollab = analyzer.institution_collaboration()
if icollab["edges"]:
    st.markdown("#### 机构合作网络")
    G2 = nx.Graph()
    for n in icollab["nodes"]:
        G2.add_node(n["id"])
    for e in icollab["edges"][:40]:
        G2.add_edge(e["source"], e["target"], weight=e["weight"])
    pos2 = nx.spring_layout(G2, k=1.5, iterations=50, seed=42)
    ex, ey = [], []
    for u, v in G2.edges():
        x0, y0 = pos2[u]; x1, y1 = pos2[v]
        ex.extend([x0, x1, None]); ey.extend([y0, y1, None])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines",
                             line=dict(width=0.5, color="#bbb"), hoverinfo="none"))
    fig.add_trace(go.Scatter(
        x=[pos2[n][0] for n in G2.nodes()], y=[pos2[n][1] for n in G2.nodes()],
        mode="markers+text", text=[n for n in G2.nodes()],
        textposition="top center", textfont=dict(size=10),
        marker=dict(size=12, color="steelblue"),
    ))
    fig.update_layout(title="机构合作网络", height=400, showlegend=False,
                      xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                      yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════ 5. 深度分析 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">🧠 深度分析</div>', unsafe_allow_html=True)

# 聚类
st.markdown("#### 📌 文献聚类")
cl1, cl2 = st.columns([3, 2])
with cl1:
    with st.spinner("正在进行文献聚类..."):
        clustering = analyzer.abstract_clustering(n_clusters=5)
    if "error" not in clustering:
        pdf = pd.DataFrame(clustering["points"])
        fig = px.scatter(pdf, x="x", y="y", color=pdf["cluster"].astype(str),
                         hover_data=["title", "year"],
                         title=f"文献聚类 ({clustering['n_clusters']}类, PCA方差:{clustering['explained_variance']:.1%})",
                         color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
with cl2:
    if "error" not in clustering:
        for cl in clustering["clusters"]:
            with st.expander(f"📌 聚类{cl['id']+1}: {', '.join(cl['keywords'][:4])} ({cl['count']}篇)"):
                for p in cl["papers"]:
                    st.markdown(f"- {p['title'][:50]} ({p['year']})")

# LDA
st.markdown("#### 🧩 LDA主题建模")
with st.spinner("正在进行LDA主题建模..."):
    lda = analyzer.lda_topics(n_topics=5)
if "error" not in lda and lda.get("topics"):
    lcols = st.columns(len(lda["topics"]))
    for i, t in enumerate(lda["topics"]):
        with lcols[i]:
            terms = "<br>".join([f"{x['word']} ({x['weight']:.2f})" for x in t["terms"][:8]])
            st.markdown(f"""<div class="card" style="text-align:center;">
            <b>主题 {t['id']+1}</b><br><small>{terms}</small></div>""", unsafe_allow_html=True)
else:
    st.info("LDA 需要更多摘要数据")

# 硕博对比 + 基金
st.markdown("---")
dd1, dd2 = st.columns(2)

with dd1:
    st.markdown("#### 🎓 硕博论文对比")
    deg = analyzer.degree_analysis()
    if deg["doctor"]["count"] > 0 and deg["master"]["count"] > 0:
        d1, d2 = st.columns(2)
        with d1:
            st.caption(f"博士论文 ({deg['doctor']['count']}篇)")
            dd = pd.DataFrame(deg["doctor"]["keywords"], columns=["关键词", "频次"])
            fig = px.bar(dd.head(8), x="频次", y="关键词", orientation="h",
                         color="频次", color_continuous_scale="Reds", title="博士高频词")
            fig.update_layout(yaxis=dict(autorange="reversed"), height=280)
            st.plotly_chart(fig, use_container_width=True)
        with d2:
            st.caption(f"硕士论文 ({deg['master']['count']}篇)")
            md = pd.DataFrame(deg["master"]["keywords"], columns=["关键词", "频次"])
            fig = px.bar(md.head(8), x="频次", y="关键词", orientation="h",
                         color="频次", color_continuous_scale="Blues", title="硕士高频词")
            fig.update_layout(yaxis=dict(autorange="reversed"), height=280)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("未检测到硕博论文数据")

with dd2:
    st.markdown("#### 💰 基金资助 & 高频词")
    fund_rank = analyzer.fund_ranking(top_n=10)
    if fund_rank:
        fdf = pd.DataFrame([{"基金": f["fund"][:40], "次数": f["count"]} for f in fund_rank])
        fig = px.bar(fdf, x="次数", y="基金", orientation="h", color="次数",
                     color_continuous_scale="Purples", title="基金资助排名")
        fig.update_layout(yaxis=dict(autorange="reversed"), height=280)
        st.plotly_chart(fig, use_container_width=True)

    # 高频词
    try:
        session = get_session()
        hotspot = HotspotAnalyzer()
        result = hotspot.analyze(session, top_n=15)
        session.close()
        if result.data.get("top_keywords_overall"):
            top_kws = result.data["top_keywords_overall"][:15]
            kw_df = pd.DataFrame(top_kws, columns=["关键词", "频次"])
            fig = px.bar(kw_df, x="频次", y="关键词", orientation="h",
                         title="Top 15 高频关键词", color="频次", color_continuous_scale="Blues")
            fig.update_layout(yaxis=dict(autorange="reversed"), height=320)
            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"热点分析失败: {e}")

# ═══════════════════ 6. 文献管理 ═══════════════════
st.markdown("---")
st.markdown('<div class="section-title">📋 文献管理</div>', unsafe_allow_html=True)

l1, l2 = st.columns([3, 2])
with l1:
    kw = st.text_input("🔎 筛选文献", placeholder="标题/关键词过滤...", label_visibility="collapsed")
    papers = analyzer.repo.search_by_keyword(keyword=kw or "")
    if papers:
        rows = [{"ID": p.id, "标题": (p.title_cn or "")[:45],
                 "作者": ", ".join([a.name for a in p.authors[:2]]),
                 "年": p.year or "-", "类型": p.degree_type or "期刊"}
                for p in papers[:200]]
        ev = st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                          on_select="rerun", selection_mode="single-row")
        if ev.selection.rows and ev.selection.rows[0] < len(papers):
            st.session_state["sel"] = papers[ev.selection.rows[0]]
        st.caption(f"共 {len(papers)} 篇")
with l2:
    st.markdown("#### 📄 文献详情")
    p = st.session_state.get("sel")
    if p:
        authors = ", ".join([a.name for a in p.authors]) or "-"
        kws = ", ".join([k.keyword for k in p.keywords]) or "-"
        abstract = (p.abstract_cn or "")[:800]
        st.markdown(f"""<div class="card">
        <h4 style="color:#1a73e8;">{(p.title_cn or '无标题')}</h4>
        <p><b>作者：</b>{authors}</p>
        <p><b>年份：</b>{p.year or '-'} | <b>学位：</b>{p.degree_type or '-'}</p>
        <p><b>来源：</b>{p.source_journal or '-'}</p>
        <p><b>关键词：</b>{kws}</p><p><b>DOI：</b>{p.doi or '-'}</p>
        <hr><p style="font-size:0.9em;">{abstract}</p></div>""", unsafe_allow_html=True)

# 导出按钮
ec1, ec2, ec3 = st.columns(3)
with ec1:
    if st.button("📥 导出 Excel", use_container_width=True):
        try:
            s = get_session()
            repo = PaperRepository(s)
            from src.analyzers.exports.excel_exporter import ExcelExporter
            ex = ExcelExporter()
            ex.add_paper_list([p.to_dict() for p in repo.search_by_keyword(keyword="")[:500]], "文献列表")
            fp = str(_project_root / "exports" / "文献导出.xlsx")
            ex.save(fp)
            st.success(f"已导出: {fp}")
            s.close()
        except Exception as e:
            st.error(str(e))
with ec2:
    if papers:
        csv = pd.DataFrame([{
            "标题": (p.title_cn or ""),
            "作者": ", ".join([a.name for a in p.authors]),
            "年份": p.year,
            "关键词": ", ".join([k.keyword for k in p.keywords]),
            "摘要": (p.abstract_cn or "")[:200],
        } for p in papers]).to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 导出 CSV", data=csv, file_name="文献导出.csv",
                           mime="text/csv", use_container_width=True)
with ec3:
    st.caption(f"v5.1 | {total}篇 | 滚动版")

# ── Footer ──
st.markdown("---")
st.caption("文献分析系统 — 上传知网导出文件 → 自动解析 → 全方位可视化分析")
