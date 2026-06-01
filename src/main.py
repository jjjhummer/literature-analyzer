"""入口文件 - CLI 和 Streamlit 启动器（纯分析版，无爬虫）"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def setup_logging(level: str = "INFO"):
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(
                _project_root / "logs" / "crawler.log",
                encoding="utf-8",
                mode="a",
            ),
        ],
    )


# ═══════════════════════════════════════════════════════════════
# CLI 命令
# ═══════════════════════════════════════════════════════════════

async def cmd_import(args):
    """CLI 导入命令 - 从知网导出文件导入文献"""
    from src.config.settings import get_settings
    from src.models.base import init_db, get_session
    from src.import_cnki import parse_file, import_to_db

    settings = get_settings()
    settings.ensure_directories()
    init_db()

    print(f"\n📂 解析文件: {args.file}")
    records = parse_file(args.file)
    if not records:
        print("❌ 未解析到任何文献记录，请检查文件格式")
        return

    print(f"   解析到 {len(records)} 条记录，正在导入...")
    session = get_session()
    try:
        new_count, skip_count = import_to_db(records, session)
        print(f"\n✅ 导入完成!")
        print(f"   新增: {new_count} 篇")
        print(f"   跳过: {skip_count} 篇 (重复)")
    finally:
        session.close()


async def cmd_analyze(args):
    """CLI 分析命令"""
    from src.models.base import init_db, get_session
    from src.analyzers.basic.yearly_trend import YearlyTrendAnalyzer
    from src.analyzers.basic.hotspot import HotspotAnalyzer

    init_db()
    session = get_session()

    try:
        # 年度趋势
        analyzer = YearlyTrendAnalyzer()
        result = analyzer.analyze(session, source=args.source)
        print(f"\n📊 {result.title}")
        print(f"   {result.description}")
        if result.data.get("years"):
            for year, count in zip(result.data["years"], result.data["counts"]):
                print(f"   {year}: {count} 篇")

        # 研究热点
        print(f"\n🔥 年度研究热点 (Top 10):")
        hotspot = HotspotAnalyzer()
        result = hotspot.analyze(session, source=args.source, top_n=10)
        if result.data.get("top_keywords_overall"):
            for kw, cnt in result.data["top_keywords_overall"]:
                print(f"   {kw}: {cnt} 次")
    finally:
        session.close()


async def cmd_stats(args):
    """CLI 统计命令"""
    from src.models.base import init_db, get_session
    from src.storage.paper_repo import PaperRepository

    init_db()
    session = get_session()
    repo = PaperRepository(session)

    try:
        total = repo.count_all()
        print(f"\n📚 数据库统计:")
        print(f"   总文献数: {total}")

        yearly = repo.get_yearly_counts(source=args.source or None)
        if yearly:
            print(f"   年份范围: {min(yearly)} - {max(yearly)}")
            for year in sorted(yearly.keys()):
                print(f"   {year}: {yearly[year]} 篇")
    finally:
        session.close()


async def cmd_init(args):
    """CLI 初始化命令"""
    from src.config.settings import get_settings
    from src.models.base import init_db

    settings = get_settings()
    settings.ensure_directories()
    init_db()

    print("✅ 数据库已初始化")
    print(f"   数据库路径: {settings.database_url}")
    print(f"   数据目录: {settings.data_dir}")


def cmd_ui(args):
    """启动 Streamlit UI"""
    import subprocess

    ui_path = _project_root / "src" / "ui" / "app.py"
    if not ui_path.exists():
        print(f"❌ UI 文件不存在: {ui_path}")
        sys.exit(1)

    print("🚀 启动 Streamlit 界面...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(ui_path),
        "--server.port", str(args.port or 8501),
    ])


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="文献分析系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.main import --file "知网导出.txt"
  python -m src.main analyze --source cnki
  python -m src.main stats
  python -m src.main ui --port 8501
  python -m src.main init
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # import
    p_import = subparsers.add_parser("import", help="导入知网导出文件")
    p_import.add_argument("--file", "-f", required=True, help="知网导出文件路径 (TXT/XLS/XLSX)")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="分析文献")
    p_analyze.add_argument("--source", "-s", default=None, help="数据源筛选")
    p_analyze.add_argument("--keyword", "-k", default=None, help="关键字筛选")

    # stats
    p_stats = subparsers.add_parser("stats", help="查看统计")
    p_stats.add_argument("--source", "-s", default=None, help="数据源筛选")

    # ui
    p_ui = subparsers.add_parser("ui", help="启动 Web 界面")
    p_ui.add_argument("--port", "-p", type=int, default=8501, help="端口号 (默认: 8501)")

    # init
    subparsers.add_parser("init", help="初始化数据库")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    setup_logging()

    if args.command == "ui":
        cmd_ui(args)
    elif args.command == "import":
        asyncio.run(cmd_import(args))
    elif args.command == "analyze":
        asyncio.run(cmd_analyze(args))
    elif args.command == "stats":
        asyncio.run(cmd_stats(args))
    elif args.command == "init":
        asyncio.run(cmd_init(args))


def cli_main():
    """setup.py 入口点"""
    main()


if __name__ == "__main__":
    main()
