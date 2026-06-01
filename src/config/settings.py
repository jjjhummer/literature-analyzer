"""全局配置管理 - 使用 pydantic-settings 加载 .env 和 YAML 配置"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_project_root() -> Path:
    """查找项目根目录（包含 pyproject.toml 的目录）"""
    current = Path(__file__).resolve().parent.parent.parent
    markers = ["pyproject.toml", ".env", "src"]
    while current != current.parent:
        if any((current / m).exists() for m in markers):
            return current
        current = current.parent
    return Path.cwd()


PROJECT_ROOT = _find_project_root()


def _load_yaml_defaults() -> dict:
    """加载 defaults.yaml 中的默认值"""
    yaml_path = Path(__file__).resolve().parent / "defaults.yaml"
    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class AnalysisSettings(BaseSettings):
    """分析配置"""
    min_docs_for_topic_modeling: int = 50
    max_topics: int = 15
    min_topics: int = 3
    default_num_topics: int = 5
    extra_stopwords_path: str = ""


class Settings(BaseSettings):
    """全局应用配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )

    # ── 项目路径 ──
    project_root: Path = Field(default=PROJECT_ROOT)
    data_dir: Path = Field(default=PROJECT_ROOT / "data")

    # ── 数据库 ──
    database_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'literature.db'}"

    # ── 日志 ──
    log_level: str = "INFO"

    # ── 子配置 ──
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)

    def __init__(self, **kwargs):
        # 先从 YAML 加载默认值
        yaml_defaults = _load_yaml_defaults()
        merged = {}
        # 扁平化 YAML 配置
        for section, values in yaml_defaults.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    merged[f"{section}_{k}" if section not in ("analysis",) else k] = v
        merged.update(kwargs)
        super().__init__(**merged)

    def ensure_directories(self):
        """确保必要的目录存在"""
        dirs = [
            self.data_dir,
            self.data_dir / "cookies",
            self.data_dir / "cache",
            self.project_root / "logs",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)


# 全局单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局 Settings 实例"""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings


def reload_settings(**overrides) -> Settings:
    """重新加载配置（支持覆盖）"""
    global _settings
    _settings = Settings(**overrides)
    _settings.ensure_directories()
    return _settings
