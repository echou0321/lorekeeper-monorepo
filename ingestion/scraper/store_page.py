import psycopg2
from config import DATABASE_URL, FANDOM_SLUG


def get_fandom_id(cur) -> str:
    cur.execute('SELECT id FROM fandoms WHERE slug = %s', (FANDOM_SLUG,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f'Fandom {FANDOM_SLUG!r} not found in DB. Was the schema seeded?')
    return str(row[0])


def upsert_page(url: str, title: str, page_type: str, raw_html: str) -> str:
    """Insert or update a page row. Returns the page UUID."""
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            fandom_id = get_fandom_id(cur)
            cur.execute('''
                INSERT INTO pages (fandom_id, page_type, title, url, raw_html)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE
                    SET raw_html = EXCLUDED.raw_html,
                        scraped_at = now()
                RETURNING id
            ''', (fandom_id, page_type, title, url, raw_html))
            page_id = str(cur.fetchone()[0])
        conn.commit()
    return page_id
