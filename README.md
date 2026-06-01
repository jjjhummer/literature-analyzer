# 📚 文献爬虫与分析系统

一个功能完整的学术文献爬虫与分析工具，支持从知网(CNKI)、Web of Science、Google Scholar 搜索文献，并提供丰富的数据分析功能。

## ✨ 功能特性

### 🔍 文献搜索
- **多源支持**: 知网 (CNKI)、Web of Science、Google Scholar
- **关键字搜索**: 支持中文/英文关键字
- **智能去重**: DOI 精确匹配 + 标题模糊匹配
- **自动分页**: 自动翻页获取所有结果
- **实时进度**: 显示爬取进度和统计

### 📊 文献分析
**基础分析**:
- 📈 年度发文量趋势
- 🔥 研究热点关键词演变
- ☁ 关键词词云

**高级分析**:
- 🧠 LDA 主题建模（自动选择最优主题数）
- 🕸 关键词共现网络
- 👨‍🏫 导师统计分析（硕博论文）
- 🏛 机构分布与合作网络

### 📥 PDF 批量下载
- 一键批量下载 PDF
- 权限检测与提示
- 下载进度追踪

## 🚀 快速开始

### 1. 安装依赖

```bash
# 克隆或下载项目
cd 知网爬虫

# 安装 Python 依赖
pip install -e .

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置环境

```bash
# 复制配置模板
copy .env.example .env

# 编辑 .env 文件，配置必要参数
# 主要配置项：
# - DATABASE_URL: 数据库路径（默认 SQLite）
# - CNKI_USERNAME / CNKI_PASSWORD: 知网登录（可选，用于获取更多权限）
# - WOS_API_KEY: Web of Science API 密钥（可选）
# - SCHOLAR_PROXY: Google Scholar 代理（可选，中国大陆用户需要）
```

### 3. 初始化数据库

```bash
python -m src.main init
# 或
python scripts/init_db.py
```

### 4. 开始使用

**CLI 命令行模式**:
```bash
# 爬取文献
python -m src.main crawl --keyword "管柱力学" --source cnki --limit 50

# 查看分析
python -m src.main analyze --source cnki

# 查看统计
python -m src.main stats
```

**Web 界面模式**:
```bash
# 启动 Streamlit 界面
python -m src.main ui --port 8501

# 浏览器访问 http://localhost:8501
```

## 📖 使用说明

### Web 界面

启动后，浏览器访问 `http://localhost:8501`，可以看到5个功能页面：

1. **🔍 文献搜索**: 输入关键字，选择数据源，点击"开始爬取"
2. **📋 文献管理**: 查看、筛选、导出已爬取的文献
3. **📊 基础分析**: 查看年度趋势、研究热点、词云
4. **🔬 高级分析**: 主题建模、关键词共现、导师/机构统计
5. **📥 批量下载**: 选择文献，批量下载 PDF

### CLI 命令行

```bash
# 完整示例流程
python -m src.main init                                    # 初始化
python -m src.main crawl -k "深度学习" -s cnki -l 100     # 爬取
python -m src.main analyze -s cnki                         # 分析
python -m src.main stats                                   # 统计
```

## ⚠ 注意事项

### 知网爬取
- 首次使用需要手动登录知网（浏览器窗口会自动打开）
- 登录成功后 Cookie 会保存24小时
- 爬取速度已做了限速（3秒/次），请勿调整过快
- 建议单次爬取不超过500篇

### PDF 下载
- 需要机构订阅权限（学校/单位的 IP 访问）
- 本软件**不会**绕过付费墙
- 下载前请先在浏览器中确认权限

### 其他数据源
- Web of Science 需要 API Key（机构申请）
- Google Scholar 在中国大陆需要代理访问

## 🏗 项目结构

```
知网爬虫/
├── src/
│   ├── config/          # 配置管理
│   ├── models/          # 数据库模型 (SQLAlchemy ORM)
│   ├── crawlers/        # 爬虫实现 (CNKI/WoS/Scholar)
│   ├── anti_detect/     # 反爬对抗模块
│   ├── storage/         # 数据持久化层
│   ├── analyzers/       # 文献分析引擎
│   ├── pipeline/        # 爬取流水线编排
│   └── ui/              # Streamlit Web 界面
├── tests/               # 测试
├── scripts/             # 工具脚本
├── data/                # 运行时数据
└── docs/                # 文档
```

## 🔧 技术栈

- **语言**: Python 3.11+
- **UI**: Streamlit
- **爬虫**: Playwright + BeautifulSoup4
- **数据库**: SQLite + SQLAlchemy
- **NLP**: jieba + gensim
- **可视化**: plotly + matplotlib + wordcloud
- **打包**: PyInstaller

## 📄 许可证

MIT License
