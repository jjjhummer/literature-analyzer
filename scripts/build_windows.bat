@echo off
REM Windows PyInstaller 打包脚本
REM 需要先安装依赖: pip install pyinstaller

echo ========================================
echo   文献爬虫系统 - Windows 打包
echo ========================================

echo.
echo [1/3] 清理旧的构建...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

echo [2/3] 执行 PyInstaller 打包...
pyinstaller ^
    --name "文献爬虫系统" ^
    --onedir ^
    --windowed ^
    --icon=NONE ^
    --add-data "src;src" ^
    --add-data "data;data" ^
    --hidden-import "streamlit" ^
    --hidden-import "playwright" ^
    --hidden-import "sqlalchemy" ^
    --hidden-import "jieba" ^
    --hidden-import "gensim" ^
    --hidden-import "plotly" ^
    --hidden-import "pandas" ^
    --hidden-import "wordcloud" ^
    --hidden-import "networkx" ^
    --hidden-import "openpyxl" ^
    --collect-all "streamlit" ^
    src/main.py

echo [3/3] 打包完成!
echo.
echo 输出目录: dist\文献爬虫系统\
echo 启动程序: dist\文献爬虫系统\main.exe ui

pause
