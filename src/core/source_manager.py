import logging
from pathlib import Path
import yaml
from .config import SourceConfig, SourcesConfig, load_sources_config

logger = logging.getLogger("pipeline")

SOURCES_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "sources.yaml"


class SourceManager:
    """读写 sources.yaml，执行数据源的添加和删除"""

    @staticmethod
    def load() -> list[SourceConfig]:
        """加载所有数据源配置"""
        return load_sources_config(SOURCES_CONFIG_PATH).sources

    @staticmethod
    def save(sources: list[SourceConfig]):
        """保存数据源配置到 sources.yaml"""
        config = SourcesConfig(sources=sources)
        with open(SOURCES_CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config.model_dump(), f, allow_unicode=True, default_flow_style=False)

    @staticmethod
    def add(source: SourceConfig):
        """添加新数据源"""
        sources = SourceManager.load()
        if any(s.id == source.id for s in sources):
            logger.warning(f"source.already_exists", extra={"source_id": source.id})
            return False
        sources.append(source)
        SourceManager.save(sources)
        logger.info(f"source.added", extra={"source_id": source.id, "type": source.type})
        return True

    @staticmethod
    def remove(source_id: str):
        """删除数据源"""
        sources = SourceManager.load()
        original_len = len(sources)
        sources = [s for s in sources if s.id != source_id]
        if len(sources) == original_len:
            logger.warning(f"source.not_found", extra={"source_id": source_id})
            return False
        SourceManager.save(sources)
        logger.info(f"source.removed", extra={"source_id": source_id})
        return True

    @staticmethod
    def get(source_id: str) -> SourceConfig | None:
        """获取指定数据源"""
        sources = SourceManager.load()
        for s in sources:
            if s.id == source_id:
                return s
        return None

    @staticmethod
    def update(source_id: str, **kwargs):
        """更新数据源配置"""
        sources = SourceManager.load()
        for i, s in enumerate(sources):
            if s.id == source_id:
                for k, v in kwargs.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
                sources[i] = s
                SourceManager.save(sources)
                return True
        return False