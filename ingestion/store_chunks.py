import psycopg2
from config import DATABASE_URL, FANDOM_SLUG


def get_arc_id_and_index(cur, arc_index: int) -> tuple[str | None, int]:
    cur.execute(
        'SELECT id, arc_index FROM arcs WHERE arc_index = %s AND fandom_id = ('
        '  SELECT id FROM fandoms WHERE slug = %s'
        ')',
        (arc_index, FANDOM_SLUG),
    )
    row = cur.fetchone()
    if not row:
        return None, arc_index
    return str(row[0]), row[1]


def store_chunks(page_id: str, chunks: list[dict]) -> None:
    """
    Each chunk dict must have:
      content, embedding, page_type, section_title, arc_index,
      spoiler_sensitive, content_type, chunk_index, token_count
    """
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM fandoms WHERE slug = %s', (FANDOM_SLUG,))
            fandom_id = str(cur.fetchone()[0])

            for chunk in chunks:
                arc_id, _ = get_arc_id_and_index(cur, chunk['arc_index'])
                embedding_str = '[' + ','.join(str(x) for x in chunk['embedding']) + ']'

                cur.execute('''
                    INSERT INTO chunks (
                        page_id, fandom_id, content, embedding, page_type,
                        section_title, arc_id, arc_index, spoiler_sensitive,
                        content_type, chunk_index, token_count
                    ) VALUES (
                        %s, %s, %s, %s::vector, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s
                    )
                ''', (
                    page_id,
                    fandom_id,
                    chunk['content'],
                    embedding_str,
                    chunk['page_type'],
                    chunk['section_title'],
                    arc_id,
                    chunk['arc_index'],
                    chunk['spoiler_sensitive'],
                    chunk['content_type'],
                    chunk['chunk_index'],
                    chunk['token_count'],
                ))
        conn.commit()
    print(f'  Stored {len(chunks)} chunks for page {page_id}')
