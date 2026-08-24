import hashlib
import random
from typing import List
import voyageai
from app.core.config import VOYAGE_API_KEY, VOYAGE_EMBED_MODEL

_DIMENSION = 1024


def _get_mock_embedding(text: str) -> List[float]:
    """Generates a deterministic, normalized 1024-dimension vector for testing
    without contacting Voyage AI."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    rng = random.Random(int(h, 16))
    vector = [rng.uniform(-1.0, 1.0) for _ in range(_DIMENSION)]
    norm = sum(x * x for x in vector) ** 0.5
    return [x / norm for x in vector] if norm > 0 else [0.0] * _DIMENSION


class EmbeddingsClient:
    """Wrapper around Voyage AI embeddings client, with a fallback mock mode
    for development and test environments."""

    def __init__(self):
        self.api_key = VOYAGE_API_KEY
        self.model = VOYAGE_EMBED_MODEL or "voyage-3"

        # Determine if we should run in mock mode
        self.is_mock = not self.api_key or self.api_key.startswith("mock")

        if not self.is_mock:
            self.client = voyageai.Client(api_key=self.api_key)
        else:
            self.client = None

    def embed_text(self, text: str, input_type: str = "document") -> List[float]:
        """Embeds a single piece of text.

        Args:
            text: The text string to embed.
            input_type: The type of context ("document" or "query").

        Returns:
            A list of floats representing the embedding vector.
        """
        if self.is_mock:
            return _get_mock_embedding(text)

        result = self.client.embed(
            [text],
            model=self.model,
            input_type=input_type,
        )
        return result.embeddings[0]

    def embed_texts(
        self, texts: List[str], input_type: str = "document"
    ) -> List[List[float]]:
        """Embeds a list of texts.

        Args:
            texts: A list of text strings to embed.
            input_type: The type of context ("document" or "query").

        Returns:
            A list of list of floats representing the embedding vectors.
        """
        if not texts:
            return []

        if self.is_mock:
            return [_get_mock_embedding(t) for t in texts]

        result = self.client.embed(
            texts,
            model=self.model,
            input_type=input_type,
        )
        return result.embeddings
