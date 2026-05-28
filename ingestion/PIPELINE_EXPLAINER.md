# Ingestion Pipeline — What It Does and Why

This document explains the ingestion pipeline from first principles. No prior web scraping experience assumed.

---

## The Big Picture

Before users can ask Lorekeeper questions, we need to build a knowledge base. That means:

1. **Scrape** — download raw wiki pages from the One Piece fandom wiki
2. **Parse** — extract clean text, organized by section (ignoring ads, nav menus, etc.)
3. **Chunk** — break sections into appropriately-sized pieces
4. **Embed** — convert each chunk into a vector (a list of numbers that represents its meaning)
5. **Store** — write chunks + vectors to the database

Once that pipeline has run, the database contains thousands of chunks, each tagged with metadata (which arc it belongs to, whether it's spoiler-sensitive, etc.) and a vector embedding. When a user asks a question, we embed their question the same way, then find the chunks whose vectors are closest — that's the retrieval step.

---

## File by File

### `run_pipeline.py` — The Entry Point

This is the only file you run directly. Everything else is a module it calls.

```bash
python run_pipeline.py --url "https://onepiece.fandom.com/wiki/Marineford_Arc" --type arc
```

It orchestrates the full flow: fetch → parse → tag → chunk → embed → store. Think of it as the conductor — it doesn't do any of the work itself, it just calls the right functions in the right order.

The `--url` flag lets you run a single page (for testing). The `--full` flag will eventually run every seed URL in the `SEED_URLS` dictionary.

---

### `config.py` — Constants and Environment Variables

Centralizes everything that might change: API keys, model names, chunk sizes, arc mappings. Loaded once, imported by every other file.

The `ARC_SECTION_MAP` is a dictionary that maps section header text to arc numbers:
```python
'marineford arc': 22,
'wano country arc': 31,
```
This is how we know that a section titled "Marineford Arc" on a character page belongs at arc index 22 in the spoiler gate. It's the manual mapping that makes the spoiler gate work for character pages.

The `SPOILER_SENSITIVE_PATTERNS` list is a set of keywords — if a section title or content contains any of these words, that chunk gets flagged `spoiler_sensitive = True`, which adds an extra 1-arc buffer in the retrieval filter.

---

### `scraper/fetch.py` — HTTP Fetching

Web scraping works by making HTTP requests to a website — exactly what your browser does when you visit a page, except your code does it programmatically. `requests` is the Python library that handles this.

Two important things here:

**1. The User-Agent header**
Websites can see who is making requests. Without a User-Agent, your request looks like a bot and may get blocked. Setting a descriptive User-Agent is courteous and reduces the chance of getting rate-limited:
```python
'User-Agent': 'Lorekeeper/1.0 (lorekeeper.app; fan research tool)'
```

**2. The delay**
```python
time.sleep(random.uniform(1.0, 2.5))
```
We wait 1–2.5 seconds between every request. This is non-negotiable. Hitting a website hundreds of times per second is a denial-of-service attack. The random component prevents a detectable fixed pattern. Fandom wikis are free resources maintained by fans — treat them politely.

---

### `scraper/parse.py` — HTML Parsing

When `fetch.py` downloads a page, it returns raw HTML — the same source code your browser renders into a visual page. It looks like:
```html
<div class="mw-parser-output">
  <h2>Summary</h2>
  <p>The Marineford Arc is the twenty-second story arc...</p>
  <h2>Story</h2>
  <p>...</p>
</div>
```

`BeautifulSoup` is a Python library that parses this HTML and lets you navigate it like a tree. We use it to:

1. **Find the content div** — all Fandom wiki content lives in `div.mw-parser-output`. Everything outside (nav, sidebar, ads) gets ignored.
2. **Remove noise** — tables (`<table>`), footnote markers (`<sup>`), navboxes, and edit links (`[edit]`) are stripped before we read any text.
3. **Split by headers** — we walk through the content element by element. When we hit an `<h2>` or `<h3>`, we save whatever we've been accumulating as a section and start a new one. This is what produces sections like `{'title': 'Marineford Arc', 'text': '...'}`.

The result is a clean list of sections, each with a title and plain text — no HTML tags.

---

### `scraper/tag.py` — Arc Tagging

Every chunk needs an `arc_index` so the spoiler gate knows whether to include it.

**For arc pages** (like the Marineford Arc page), the entire page belongs to one arc. `infer_arc_index_for_page()` in `run_pipeline.py` looks up the arc index from the page title.

**For character pages** (like Portgas D. Ace), each section belongs to a different arc. A section titled "Marineford Arc" gets `arc_index = 22`. A section titled "Personality" gets tagged to the character's introduction arc (conservative default — we'd rather show something early than spoil something late).

`is_spoiler_sensitive()` checks whether the section title or content contains any of the patterns in `SPOILER_SENSITIVE_PATTERNS`. If it does, the chunk gets `spoiler_sensitive = True`.

---

### `scraper/store_page.py` — Saving the Raw Page

After fetching, we save the raw HTML to the `pages` table in the database before doing anything else.

Why? Because parsing and chunking logic will change as we improve it. If we only stored chunks, improving the chunker would require re-scraping all 500+ wiki pages. Storing raw HTML means we can re-chunk from the database without making a single HTTP request.

The `ON CONFLICT (url) DO UPDATE` clause is an "upsert" — if a page with this URL already exists (from a previous run), update it instead of erroring. Safe to re-run.

---

### `chunk.py` — Chunking

Chunks are the atomic unit of the knowledge base. Each one is a piece of text small enough to embed as a single vector and large enough to carry meaningful context.

**Why not just embed entire sections?**
Sections can be thousands of words long. Embedding models have token limits, and long inputs produce averaged-out embeddings that lose specificity. A 4,000-word section about the entire Marineford Arc will match a lot of queries vaguely rather than matching specific queries precisely.

**Why 450 tokens?**
It's a common sweet spot — enough context for coherent meaning, small enough for precise retrieval. One token ≈ 0.75 words in English.

**The overlap (50 tokens)**
When we split a long section into chunks, we slide the window back 50 tokens before starting the next chunk. This means the end of chunk 1 and the start of chunk 2 share 50 tokens of content. Without overlap, a sentence split across a chunk boundary would be half-incoherent in both chunks.

**Sections under 100 tokens**
Short sections (like a one-paragraph ability description) are kept as a single chunk rather than being split. Splitting a 60-token section would produce meaningless fragments.

`tiktoken` is OpenAI's tokenizer library — it counts tokens accurately for cl100k_base, which is a good approximation for Voyage AI's tokenizer as well.

---

### `embed.py` — Embedding

An embedding is a way of representing the meaning of text as a point in a high-dimensional space. Voyage AI's `voyage-3` model converts a string of text into a list of 1024 floating-point numbers. Two chunks about the same topic will have vectors that point in similar directions — that's what makes semantic search work.

```python
result = client.embed(batch, model='voyage-3')
```

We batch up to 128 chunks per API call. Calling the API once per chunk would be extremely slow (thousands of HTTP round trips) and would hit rate limits. Batching reduces it to tens of calls.

The embeddings are just Python lists of floats at this point. They get stored in the database as `vector(1024)` — the pgvector column type that supports similarity search.

---

### `store_chunks.py` — Writing to the Database

After chunking and embedding, we write each chunk to the `chunks` table. The key part:

```python
embedding_str = '[' + ','.join(str(x) for x in chunk['embedding']) + ']'
cur.execute('... %s::vector ...', (..., embedding_str, ...))
```

PostgreSQL's pgvector extension doesn't accept a Python list directly — we convert it to a string in the format `[0.123, -0.456, ...]` and cast it to `vector` in the SQL. Once stored, pgvector can do cosine similarity search across all vectors in milliseconds using the HNSW index we created in the schema.

---

## The Flow End to End

```
Wiki URL
  └─ fetch.py          → raw HTML string
       └─ parse.py     → list of {title, text, level} sections
            └─ tag.py  → arc_index + spoiler_sensitive per section
                 └─ chunk.py      → list of text chunks per section
                      └─ embed.py → list of 1024-float vectors
                           └─ store_chunks.py → rows in chunks table
```

After one page runs, the database has:
- 1 row in `pages` (the raw HTML)
- N rows in `chunks` (one per chunk, each with an embedding and full metadata)

After the full pipeline runs across all seed URLs, the database has thousands of chunks — the complete, spoiler-tagged, searchable knowledge base that the API queries against.
