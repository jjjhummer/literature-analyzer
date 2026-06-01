"""文献分析系统 - Hugging Face Spaces / Streamlit Cloud 入口"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 直接执行主应用
with open(Path(__file__).resolve().parent / "src" / "ui" / "app.py", encoding="utf-8") as f:
    exec(f.read())
