"""中文文本预处理流水线 - 用于分析前的数据清洗"""

import logging
import os
import re
from typing import Optional

import jieba

logger = logging.getLogger(__name__)

# 哈工大停用词表（精简版）+ 自定义领域停用词
_DEFAULT_STOPWORDS = {
    # 通用停用词
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "所", "为", "所以", "因为", "但是", "然而", "而且", "虽然", "如果",
    "可以", "这个", "那个", "什么", "哪", "怎样", "怎么", "为何",
    "之", "与", "及", "其", "或", "并", "等", "从", "被", "把",
    "让", "给", "向", "对", "以", "通过", "根据", "关于", "对于",
    # 学术文本停用词
    "本文", "研究", "进行", "分析", "结果", "表明", "发现", "采用",
    "提出", "建立", "利用", "方法", "问题", "方面", "不同", "主要",
    "存在", "具有", "影响", "作用", "发展", "过程", "技术", "系统",
    "基于", "一种", "提出", "该", "其", "本", "论文", "实验",
    "目前", "近年", "以来", "以后", "一定", "可能", "需要",
    "其中", "之间", "之后", "之前", "包括", "以及", "使用",
    # 英文
    "the", "a", "an", "of", "in", "on", "to", "for", "with", "and",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "shall", "can", "need", "dare", "ought", "used",
    "it", "its", "this", "that", "these", "those", "we", "you", "they",
    "he", "she", "his", "her", "their", "them", "my", "our", "your",
}
# 单字符 + 纯数字正则
_SINGLE_CHAR_PATTERN = re.compile(r'^.$')
_PURE_NUMBER_PATTERN = re.compile(r'^\d+(\.\d+)?$')

# 中英文正则（只保留中英文字符和数字）
_CLEAN_PATTERN = re.compile(r'[^一-龥a-zA-Z0-9\s]')


def load_stopwords(extra_path: Optional[str] = None) -> set[str]:
    """加载停用词表"""
    stopwords = set(_DEFAULT_STOPWORDS)

    if extra_path and os.path.exists(extra_path):
        with open(extra_path, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:
                    stopwords.add(word)
        logger.info(f"从 {extra_path} 加载了额外停用词")

    return stopwords


def preprocess_text(
    text: str,
    stopwords: Optional[set[str]] = None,
    add_domain_words: Optional[list[str]] = None,
) -> list[str]:
    """中文文本预处理流水线

    处理步骤：
    1. 去除 HTML 标签和特殊字符
    2. jieba 精确模式分词
    3. 去除停用词
    4. 去除单字符和纯数字
    5. (可选) 加载领域词典

    Args:
        text: 原始文本
        stopwords: 停用词集合（None则使用默认）
        add_domain_words: 额外的领域词汇（加入 jieba 词典）

    Returns:
        预处理后的词条列表
    """
    if not text:
        return []

    # 1. 清洗文本
    text = _CLEAN_PATTERN.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []

    # 2. 加载领域词典
    if add_domain_words:
        for word in add_domain_words:
            jieba.add_word(word)

    # 3. 分词
    tokens = jieba.lcut(text, cut_all=False)

    # 4. 去除停用词和噪声
    sw = stopwords if stopwords is not None else _DEFAULT_STOPWORDS
    cleaned = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token in sw:
            continue
        if _SINGLE_CHAR_PATTERN.match(token):
            continue
        if _PURE_NUMBER_PATTERN.match(token):
            continue
        cleaned.append(token)

    return cleaned


def batch_preprocess(
    texts: list[str],
    stopwords: Optional[set[str]] = None,
    add_domain_words: Optional[list[str]] = None,
) -> list[list[str]]:
    """批量预处理文本"""
    return [preprocess_text(t, stopwords, add_domain_words) for t in texts]
