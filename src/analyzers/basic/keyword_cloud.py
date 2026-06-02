"""关键词词云生成"""

import io
import logging
import os
from typing import Optional
from collections import defaultdict

# ⚠️ 必须在 import pyplot 前设置 Agg 后端（Linux headless 环境兼容）
import matplotlib
matplotlib.use("Agg")

from sqlalchemy.orm import Session
from wordcloud import WordCloud
import matplotlib.pyplot as plt

from src.analyzers.base import AbstractAnalyzer, AnalysisResult
from src.storage.paper_repo import PaperRepository

logger = logging.getLogger(__name__)

# 尝试加载中文字体
_FONT_PATH = None
_CANDIDATE_FONTS = [
    # Windows
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/STSONG.TTF",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    # Linux - Noto CJK
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Linux - WenQuanYi (Streamlit Cloud via packages.txt)
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
    # Linux - Droid Sans Fallback
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

def _find_chinese_font():
    """Locate a usable Chinese font across platforms."""
    # 1. Try known paths
    for font_path in _CANDIDATE_FONTS:
        if os.path.exists(font_path):
            logger.info(f"✅ 中文字体: {font_path}")
            return font_path
    # 2. fc-list (Linux)
    try:
        import subprocess
        result = subprocess.run(["fc-list", ":lang=zh", "file"],
                              capture_output=True, text=True, timeout=5)
        for line in result.stdout.strip().split("\n"):
            if ":" in line:
                path = line.split(":")[0].strip()
                if os.path.exists(path):
                    logger.info(f"✅ fc-list 中文字体: {path}")
                    return path
    except Exception:
        pass
    # 3. Glob search common font dirs
    try:
        import glob as glob_mod
        for root in ["/usr/share/fonts", "/usr/local/share/fonts"]:
            for pat in ["**/*.ttc", "**/*.ttf", "**/*.otf"]:
                for fpath in glob_mod.glob(os.path.join(root, pat), recursive=True):
                    if os.path.exists(fpath):
                        logger.info(f"✅ glob 字体: {fpath}")
                        return fpath
    except Exception:
        pass
    logger.warning("⚠️ 未找到中文字体，词云可能无法正常显示中文")
    return None

_FONT_PATH = _find_chinese_font()


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
