#!/usr/bin/env python
"""数据库初始化脚本 - 创建所有表"""

import sys
from pathlib import Path

# 添加项目根目录到 Python Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.settings import get_settings
from src.models.base import init_db


def main():
    """初始化数据库"""
    print("=" * 50)
    print("  文献分析系统 - 数据库初始化")
    print("=" * 50)

    settings = get_settings()
    settings.ensure_directories()

    print(f"\n数据目录: {settings.data_dir}")
    print(f"数据库:   {settings.database_url}")

    init_db()

    print("\n数据库初始化完成!")
    print(f"\n下一步:")
    print(f"  python -m src.main import --file \"知网导出文件.txt\"")
    print(f"  python -m src.main ui")
    print()


if __name__ == "__main__":
    main()
