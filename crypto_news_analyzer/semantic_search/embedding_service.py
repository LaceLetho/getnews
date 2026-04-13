"""Dedicated embedding service for semantic search."""

from collections.abc import Sequence
import logging
from typing import Any, List, Optional, cast

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from ..models import ContentItem

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates article embeddings without relying on LLMAnalyzer."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int = 1536):
        self.api_key: str = (api_key or "").strip()
        self.model: str = (model or "").strip() or "text-embedding-3-small"
        self.dimensions: int = dimensions
        self.client: Optional[Any] = None

        if not self.api_key:
            logger.info("OPENAI_API_KEY未配置，EmbeddingService将保持禁用")
            return

        if OpenAI is None:
            logger.warning("openai package未安装，EmbeddingService将保持禁用")
            return

        try:
            self.client = OpenAI(api_key=self.api_key)
        except Exception as exc:
            logger.warning(f"初始化EmbeddingService失败: {exc}")
            self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def build_input_text(self, item: ContentItem) -> str:
        return f"{item.title}\n\n{item.content}"

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not self.enabled:
            return None

        try:
            client = cast(Any, self.client)
            response = client.embeddings.create(model=self.model, input=text)
            data = getattr(response, "data", None) or []
            if not data:
                logger.warning("Embedding API返回空响应")
                return None

            embedding = list(getattr(data[0], "embedding", None) or [])
            if len(embedding) != self.dimensions:
                logger.warning(
                    "Embedding维度不匹配: expected=%s actual=%s model=%s",
                    self.dimensions,
                    len(embedding),
                    self.model,
                )
                return None

            return [float(value) for value in embedding]
        except Exception as exc:
            logger.warning(f"生成Embedding失败: {exc}")
            return None

    def generate_for_content_item(self, item: ContentItem) -> Optional[List[float]]:
        return self.generate_embedding(self.build_input_text(item))

    def generate_for_content_items(
        self, items: Sequence[ContentItem]
    ) -> List[Optional[List[float]]]:
        if not items:
            return []
        if not self.enabled:
            return [None for _ in items]

        try:
            client = cast(Any, self.client)
            response = client.embeddings.create(
                model=self.model,
                input=[self.build_input_text(item) for item in items],
            )
            data = list(getattr(response, "data", None) or [])
            if len(data) != len(items):
                logger.warning(
                    "批量Embedding返回数量不匹配: expected=%s actual=%s model=%s",
                    len(items),
                    len(data),
                    self.model,
                )
                return [None for _ in items]

            results: List[Optional[List[float]]] = []
            for item, row in zip(items, data):
                embedding = list(getattr(row, "embedding", None) or [])
                if len(embedding) != self.dimensions:
                    logger.warning(
                        "内容 %s 的Embedding维度不匹配: expected=%s actual=%s model=%s",
                        item.id,
                        self.dimensions,
                        len(embedding),
                        self.model,
                    )
                    results.append(None)
                    continue

                results.append([float(value) for value in embedding])

            return results
        except Exception as exc:
            logger.warning(f"批量生成Embedding失败: {exc}")
            return [None for _ in items]
