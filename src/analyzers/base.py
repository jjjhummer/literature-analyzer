"""分析器抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session


@dataclass
class AnalysisResult:
    """分析结果"""
    analysis_type: str                    # 分析类型名称
    title: str                            # 结果标题
    data: Any = None                      # 主要数据
    chart_data: Any = None                # 图表数据
    description: str = ""                 # 结果描述
    warnings: list[str] = field(default_factory=list)


class AbstractAnalyzer(ABC):
    """分析器抽象基类"""

    @abstractmethod
    def analyze(self, session: Session, **kwargs) -> AnalysisResult:
        """执行分析

        Args:
            session: 数据库会话
            **kwargs: 分析参数（如关键字、年份范围等）

        Returns:
            AnalysisResult
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """分析器名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """分析器描述"""
        ...
