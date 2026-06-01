"""Streamlit Session State 管理"""

from dataclasses import dataclass, field
from typing import Optional

import streamlit as st


@dataclass
class AppState:
    """全局应用状态"""

    # 搜索
    keyword: str = ""
    selected_sources: list[str] = field(default_factory=lambda: ["cnki"])
    search_limit: int = 50

    # 爬取状态
    is_crawling: bool = False
    crawl_progress: dict = field(default_factory=dict)

    # 当前会话
    current_session_id: Optional[int] = None

    # 选中的文献
    selected_paper_ids: list[int] = field(default_factory=list)

    # 分析参数
    analysis_keyword: str = ""
    analysis_source: Optional[str] = None
    analysis_degree_type: Optional[str] = None


def init_state():
    """初始化 Session State"""
    if "app_state" not in st.session_state:
        st.session_state.app_state = AppState()

    # 确保默认值
    defaults = {
        "keyword": "",
        "selected_sources": ["cnki"],
        "search_limit": 50,
        "is_crawling": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_state() -> AppState:
    """获取当前应用状态"""
    init_state()
    return st.session_state.app_state


def reset_search():
    """重置搜索状态"""
    state = get_state()
    state.is_crawling = False
    state.crawl_progress = {}
    state.current_session_id = None
