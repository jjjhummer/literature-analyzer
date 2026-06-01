"""知网导出文件解析器 - 支持 TXT 和 XLS(HTML) 格式"""

import json
import re
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class CnkiRecord:
    """知网文献记录"""
    src_database: str = ""       # 来源库 (期刊/博士/硕士)
    title: str = ""              # 题名
    author: str = ""             # 作者
    organ: str = ""              # 单位
    source: str = ""             # 文献来源
    keyword: str = ""            # 关键词 (分号分隔)
    summary: str = ""            # 摘要
    pub_time: str = ""           # 发表时间
    first_duty: str = ""         # 第一责任人
    fund: str = ""               # 基金
    year: str = ""               # 年
    volume: str = ""             # 卷
    period: str = ""             # 期
    page_count: str = ""         # 页码
    clc: str = ""                # 中图分类号
    url: str = ""                # 网址
    doi: str = ""                # DOI

    def extract_year(self) -> Optional[int]:
        """从pub_time或year字段提取年份数字"""
        if self.year:
            m = re.search(r'(\d{4})', str(self.year))
            if m:
                return int(m.group(1))
        if self.pub_time:
            m = re.search(r'(\d{4})', self.pub_time)
            if m:
                return int(m.group(1))
        return None

    def extract_authors(self) -> list[str]:
        """解析作者列表"""
        if not self.author:
            return []
        return [a.strip() for a in re.split(r'[;；]', self.author) if a.strip()]

    def extract_keywords(self) -> list[str]:
        """解析关键词列表"""
        if not self.keyword:
            return []
        return [k.strip() for k in re.split(r'[;；]', self.keyword) if k.strip()]

    def extract_degree_type(self) -> Optional[str]:
        """从来源库推断学位类型"""
        db = self.src_database
        if "博士" in db:
            return "博士"
        if "硕士" in db:
            return "硕士"
        return None

    def is_thesis(self) -> bool:
        """判断是否为学位论文"""
        return self.extract_degree_type() is not None


def parse_txt(filepath: str) -> list[CnkiRecord]:
    """解析知网 TXT 导出文件

    TXT格式示例:
        SrcDatabase-来源库: 博士
        Title-题名: xxx
        ...
        DOI-DOI: xxx
        (空行分隔)
    """
    records = []
    current = {}
    field_map = {
        "SrcDatabase": "src_database", "Title": "title",
        "Author": "author", "Organ": "organ", "Source": "source",
        "Keyword": "keyword", "Summary": "summary",
        "PubTime": "pub_time", "FirstDuty": "first_duty",
        "Fund": "fund", "Year": "year", "Volume": "volume",
        "Period": "period", "PageCount": "page_count",
        "CLC": "clc", "URL": "url", "DOI": "doi",
    }

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                # 空行 = 记录分隔
                if current:
                    records.append(CnkiRecord(**current))
                    current = {}
                continue

            # 解析 "Field-中文: value"
            m = re.match(r'^(\w+)-[^:]*:\s*(.*)', line)
            if m:
                field = m.group(1)
                value = m.group(2).strip()
                if field in field_map:
                    current[field_map[field]] = value

        # 最后一条
        if current:
            records.append(CnkiRecord(**current))

    logger.info(f"TXT解析完成: {len(records)} 条记录")
    return records


def parse_xls(filepath: str) -> list[CnkiRecord]:
    """解析知网 XLS 导出文件（本质是HTML table）"""
    records = []

    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        logger.error("XLS文件中未找到表格")
        return records

    rows = table.find_all("tr")
    if len(rows) < 2:
        return records

    # 解析表头
    header_cells = rows[0].find_all(["td", "th"])
    col_map = {}  # index -> field_name
    cn_to_en = {
        "SrcDatabase": "src_database", "Title": "title",
        "Author": "author", "Organ": "organ", "Source": "source",
        "Keyword": "keyword", "Summary": "summary",
        "PubTime": "pub_time", "FirstDuty": "first_duty",
        "Fund": "fund", "Year": "year", "Volume": "volume",
        "Period": "period", "PageCount": "page_count",
        "CLC": "clc", "URL": "url", "DOI": "doi",
    }

    for i, cell in enumerate(header_cells):
        text = cell.get_text(strip=True)
        for cn_key, en_key in cn_to_en.items():
            if cn_key.lower() in text.lower():
                col_map[i] = en_key
                break

    # 解析数据
    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue

        data = {}
        for i, cell in enumerate(cells):
            if i in col_map:
                data[col_map[i]] = cell.get_text(strip=True)

        if data.get("title"):
            records.append(CnkiRecord(**data))

    logger.info(f"XLS解析完成: {len(records)} 条记录")
    return records


def parse_file(filepath: str) -> list[CnkiRecord]:
    """自动识别格式并解析"""
    path = Path(filepath)
    ext = path.suffix.lower()

    if ext in (".txt",):
        return parse_txt(filepath)
    elif ext in (".xls", ".xlsx"):
        # 先尝试pandas读取
        try:
            df = pd.read_excel(filepath)
            return _parse_dataframe(df)
        except Exception:
            pass
        # 回退到HTML解析
        return parse_xls(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def _parse_dataframe(df: pd.DataFrame) -> list[CnkiRecord]:
    """从pandas DataFrame解析"""
    records = []
    col_map = {
        "SrcDatabase": "src_database", "Title": "title",
        "Author": "author", "Organ": "organ", "Source": "source",
        "Keyword": "keyword", "Summary": "summary",
        "PubTime": "pub_time", "FirstDuty": "first_duty",
        "Fund": "fund", "Year": "year", "Volume": "volume",
        "Period": "period", "PageCount": "page_count",
        "CLC": "clc", "URL": "url", "DOI": "doi",
    }

    for _, row in df.iterrows():
        data = {}
        for col in df.columns:
            # 模糊匹配列名
            for cn_key, en_key in col_map.items():
                if cn_key.lower() in str(col).lower():
                    val = row[col]
                    data[en_key] = str(val) if pd.notna(val) else ""
                    break
        if data.get("title"):
            records.append(CnkiRecord(**data))

    logger.info(f"DataFrame解析完成: {len(records)} 条记录")
    return records


def import_to_db(records: list[CnkiRecord], session=None):
    """将解析后的记录导入数据库"""
    if session is None:
        from src.models.base import get_session
        session = get_session()

    from src.storage.paper_repo import (
        PaperRepository, AuthorRepository, KeywordRepository,
        InstitutionRepository, AdvisorRepository,
    )
    from src.models.paper import Paper

    paper_repo = PaperRepository(session)
    author_repo = AuthorRepository(session)
    keyword_repo = KeywordRepository(session)
    inst_repo = InstitutionRepository(session)
    advisor_repo = AdvisorRepository(session)

    new_count = 0
    skip_count = 0

    for rec in records:
        # 去重检查
        doi = rec.doi.strip() if rec.doi else None
        title = rec.title.strip() if rec.title else None

        # 1) DOI 精确匹配
        if doi:
            existing = paper_repo.find_by_doi(doi)
            if existing:
                skip_count += 1
                continue

        # 2) 标题模糊匹配（无DOI或有DOI但未命中时兜底）
        if title:
            existing = paper_repo.find_by_title_fuzzy(title, threshold=0.85)
            if existing:
                skip_count += 1
                continue

        # 创建Paper
        year = rec.extract_year()
        degree_type = rec.extract_degree_type()
        article_type = "thesis" if degree_type else "journal"

        paper = Paper(
            source="cnki",
            source_id=None,
            title_cn=rec.title or None,
            abstract_cn=rec.summary or None,
            doi=doi,
            year=year,
            source_journal=rec.source or rec.organ or None,
            degree_type=degree_type,
            article_type=article_type,
            url=rec.url or None,
        )
        session.add(paper)  # 先加入session，避免关联时SAWarning

        # 作者
        for a_name in rec.extract_authors():
            author, _ = author_repo.get_or_create_by_name(a_name)
            paper.authors.append(author)

        # 关键词
        for kw in rec.extract_keywords():
            kw_obj, _ = keyword_repo.get_or_create_by_keyword(kw)
            paper.keywords.append(kw_obj)

        # 机构
        if rec.organ:
            inst, _ = inst_repo.get_or_create_by_name(rec.organ)
            paper.institutions.append(inst)

        # 导师（第一责任人可能是导师）
        if rec.first_duty and degree_type:
            advisor, _ = advisor_repo.get_or_create_by_name(rec.first_duty)
            paper.advisors.append(advisor)

        # 存储基金等信息到extra_data
        extra = {}
        if rec.fund:
            extra["fund"] = rec.fund
        if rec.first_duty:
            extra["first_duty"] = rec.first_duty
        if rec.clc:
            extra["clc"] = rec.clc
        if extra:
            paper.extra_data = json.dumps(extra, ensure_ascii=False)

        new_count += 1

    session.commit()
    logger.info(f"导入完成: 新增{new_count}, 跳过{skip_count}")
    return new_count, skip_count
