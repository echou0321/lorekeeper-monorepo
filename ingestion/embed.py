import voyageai
from config import VOYAGE_API_KEY, EMBEDDING_MODEL

client = voyageai.Client(api_key=VOYAGE_API_KEY)

BATCH_SIZE = 128


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings in batches. Returns one embedding per input."""
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        result = client.embed(batch, model=EMBEDDING_MODEL)
        all_embeddings.extend(result.embeddings)
    return all_embeddings
