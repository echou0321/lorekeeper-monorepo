"""
Lorekeeper ingestion pipeline.

Usage:
  # Single test page
  python run_pipeline.py --url "https://onepiece.fandom.com/wiki/Marineford_Arc" --type arc

  # Full run (all seed URLs)
  python run_pipeline.py --full
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from scraper.fetch import fetch
from scraper.parse import extract_sections
from scraper.tag import tag_section, is_spoiler_sensitive
from scraper.store_page import upsert_page
from chunk import chunk_section, count_tokens
from embed import embed_texts
from store_chunks import store_chunks
from config import ARC_SECTION_MAP

SEED_URLS = {
    'arc': [
        'https://onepiece.fandom.com/wiki/Marineford_Arc',
        # expand to full arc list after single-page test passes
    ],
    'character': [],
    'devil_fruit': [],
    'crew': [],
    'concept': [],
}


def infer_arc_index_for_page(page_type: str, page_title: str) -> int:
    """
    For arc pages, look up the arc_index from the title.
    For other page types, return 1 as a safe default (overridden per-section).
    """
    if page_type == 'arc':
        normalized = page_title.lower().replace('_', ' ').replace('-', ' ')
        for key, idx in ARC_SECTION_MAP.items():
            if key in normalized:
                return idx
    return 1


def infer_content_type(page_type: str, section_title: str) -> str:
    if page_type == 'arc':
        return 'arc_summary'
    if page_type == 'devil_fruit':
        return 'devil_fruit'
    if page_type == 'crew':
        return 'crew'
    title_lower = section_title.lower()
    if 'abilit' in title_lower or 'power' in title_lower or 'haki' in title_lower:
        return 'ability'
    if 'quote' in title_lower:
        return 'quote'
    return 'character_history'


def process_page(url: str, page_type: str) -> None:
    print(f'\nFetching {url}')
    html = fetch(url)

    title = url.rstrip('/').split('/')[-1].replace('_', ' ')
    page_id = upsert_page(url, title, page_type, html)
    print(f'  Stored page: {title} ({page_id})')

    sections = extract_sections(html)
    print(f'  Extracted {len(sections)} sections')

    intro_arc_index = infer_arc_index_for_page(page_type, title)

    chunk_dicts = []
    chunk_index = 0

    for section in sections:
        arc_index = tag_section(section['title'], intro_arc_index)
        spoiler = is_spoiler_sensitive(section['title'], section['text'])
        content_type = infer_content_type(page_type, section['title'])
        sub_chunks = chunk_section(section['text'])

        for text in sub_chunks:
            chunk_dicts.append({
                'content':          text,
                'page_type':        page_type,
                'section_title':    section['title'],
                'arc_index':        arc_index,
                'spoiler_sensitive': spoiler,
                'content_type':     content_type,
                'chunk_index':      chunk_index,
                'token_count':      count_tokens(text),
                'embedding':        None,  # filled below
            })
            chunk_index += 1

    print(f'  Chunked into {len(chunk_dicts)} chunks — embedding...')
    embeddings = embed_texts([c['content'] for c in chunk_dicts])
    for c, emb in zip(chunk_dicts, embeddings):
        c['embedding'] = emb

    store_chunks(page_id, chunk_dicts)
    print(f'  Done: {url}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url',  help='Single page URL to process')
    parser.add_argument('--type', help='Page type (arc, character, devil_fruit, crew, concept)',
                        default='arc')
    parser.add_argument('--full', action='store_true',
                        help='Run full pipeline across all seed URLs')
    args = parser.parse_args()

    if args.url:
        process_page(args.url, args.type)
    elif args.full:
        for page_type, urls in SEED_URLS.items():
            for url in urls:
                process_page(url, page_type)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
