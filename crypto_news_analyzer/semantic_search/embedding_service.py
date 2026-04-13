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

    _TOKEN_LIMIT_ERROR_SNIPPETS = (
        "maximum input length is 8192 tokens",
        "context length",
    )
    _TRUNCATION_CHAR_LIMITS = (12000, 8000, 4000)

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
    ):
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

    def _is_length_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return any(snippet in message for snippet in self._TOKEN_LIMIT_ERROR_SNIPPETS)

    def _truncate_text(self, text: str, max_chars: int) -> str:
        normalized = str(text or "")
        if len(normalized) <= max_chars:
            return normalized

        if max_chars <= 32:
            return normalized[:max_chars]

        head_chars = max_chars // 2
        tail_chars = max_chars - head_chars - 1
        return f"{normalized[:head_chars]}\n{normalized[-tail_chars:]}"

    def _extract_embedding(self, response: Any) -> Optional[List[float]]:
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

    def _request_embedding(self, text: str) -> Optional[List[float]]:
        client = cast(Any, self.client)
        response = client.embeddings.create(model=self.model, input=text)
        return self._extract_embedding(response)

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not self.enabled:
            return None

        try:
            return self._request_embedding(text)
        except Exception as exc:
            if self._is_length_limit_error(exc):
                for limit in self._TRUNCATION_CHAR_LIMITS:
                    truncated_text = self._truncate_text(text, limit)
                    if truncated_text == text:
                        continue

                    try:
                        logger.warning(
                            "Embedding输入超长，尝试截断后重试: model=%s chars=%s->%s",
                            self.model,
                            len(text),
                            len(truncated_text),
                        )
                        return self._request_embedding(truncated_text)
                    except Exception as retry_exc:
                        if not self._is_length_limit_error(retry_exc):
                            logger.warning(f"截断后生成Embedding失败: {retry_exc}")
                            return None

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
            if self._is_length_limit_error(exc):
                logger.warning("批量Embedding包含超长内容，回退到逐条处理: %s", exc)
                return [self.generate_for_content_item(item) for item in items]
            logger.warning(f"批量生成Embedding失败: {exc}")
            return [None for _ in items]
