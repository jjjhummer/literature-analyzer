"""关键词词云生成"""

import io
import logging
from typing import Optional
from collections import defaultdict

from sqlalchemy.orm import Session
from wordcloud import WordCloud
import matplotlib.pyplot as plt

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.storage.paper_repo import PaperRepository

logger = logging.getLogger(__name__)

# 尝试加载中文字体
_FONT_PATH = None
_CANDIDATE_FONTS = [
    "C:/Windows/Fonts/simhei.ttf",          # 黑体
    "C:/Windows/Fonts/msyh.ttc",            # 微软雅黑
    "C:/Windows/Fonts/simsun.ttc",          # 宋体
    "C:/Windows/Fonts/STSONG.TTF",          # 华文宋体
    "/System/Library/Fonts/PingFang.ttc",   # macOS
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",  # Linux
]

import os
for font_path in _CANDIDATE_FONTS:
    if os.path.exists(font_path):
        _FONT_PATH = font_path
        break


class KeywordCloudAnalyzer(AbstractAnalyzer):
    """词云分析器

    根据关键词频率生成词云图片。
    """

    name = "keyword_cloud"
    description = "关键词词云"

    def analyze(
        self,
        session: Session,
        source: Optional[str] = None,
        max_words: int = 200,
        width: int = 800,
        height: int = 600,
        background_color: str = "white",
        **kwargs,
    ) -> AnalysisResult:
        """生成关键词词云

        Args:
            session: 数据库会话
            source: 数据源筛选
            max_words: 最大词数
            width: 图片宽度
            height: 图片高度
            background_color: 背景颜色

        Returns:
            result.data["image_base64"] 包含 base64 编码的 PNG 图片
        """
        repo = PaperRepository(session)
        kw_counts = repo.get_all_keywords_count(source=source, limit=max_words)

        if not kw_counts:
            return AnalysisResult(
                analysis_type=self.name,
                title="关键词词云",
                data={},
                description="暂无数据",
                warnings=["数据库中没有关键词数据"],
            )

        # 构建词频字典
        freq_dict = {kw: float(cnt) for kw, cnt in kw_counts}

        # 生成词云
        try:
            wc = WordCloud(
                font_path=_FONT_PATH,
                width=width,
                height=height,
                background_color=background_color,
                max_words=max_words,
                collocations=False,
                scale=2,  # 提高清晰度
            )
            wc.generate_from_frequencies(freq_dict)

            # 转为图片
            fig, ax = plt.subplots(figsize=(width / 100, height / 100), dpi=100)
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            plt.tight_layout(pad=0)

            # 保存为 PNG bytes
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0)
            buf.seek(0)
            plt.close()

            import base64
            img_base64 = base64.b64encode(buf.read()).decode("utf-8")

            top_kws = [f"{kw}({int(cnt)})" for kw, cnt in kw_counts[:10]]
            desc = f"共 {len(freq_dict)} 个关键词\nTop 10: {', '.join(top_kws)}"

            return AnalysisResult(
                analysis_type=self.name,
                title="关键词词云",
                data={
                    "image_base64": img_base64,
                    "frequencies": freq_dict,
                    "font_used": _FONT_PATH,
                },
                description=desc,
            )

        except Exception as e:
            logger.error(f"生成词云失败: {e}")
            return AnalysisResult(
                analysis_type=self.name,
                title="关键词词云",
                data={"frequencies": freq_dict},
                description=f"词云生成失败: {e}",
                warnings=[f"词云生成错误: {e}"],
            )
