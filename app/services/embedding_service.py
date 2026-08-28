from ollama import AsyncClient

from app.core.config import settings

ollama_client = AsyncClient()


async def generate_embedding(text: str) -> list[float]:
    """
    Generate an embedding for the given text using the Ollama API.

    """
    response = await ollama_client.embed(model=settings.EMBED_MODEL, input=text)

    embedding = response["embeddings"][0]

    return embedding
