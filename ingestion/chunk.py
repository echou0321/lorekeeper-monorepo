import tiktoken
from config import CHUNK_SIZE, CHUNK_OVERLAP, MIN_CHUNK_TOKENS

encoder = tiktoken.get_encoding('cl100k_base')


def chunk_section(text: str) -> list[str]:
    tokens = encoder.encode(text)

    if len(tokens) <= MIN_CHUNK_TOKENS:
        return [text]

    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunks.append(encoder.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = end - CHUNK_OVERLAP

    return chunks


def count_tokens(text: str) -> int:
    return len(encoder.encode(text))
