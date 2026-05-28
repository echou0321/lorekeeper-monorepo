# Lorekeeper — Technical Design Doc: Weeks 1 & 2

## Overview

This document covers the full pipeline from wiki scraping to a working query API. Week 1 builds the corpus. Week 2 builds the retrieval and generation layer on top of it. These are designed together because upstream schema decisions directly constrain downstream retrieval logic.

---

## Stack

| Layer | Technology | Rationale |
|---|---|---|
| Scraping | Python + BeautifulSoup | RAG/ML ecosystem is Python-native |
| Backend API | FastAPI | Async, lightweight, built-in streaming support |
| Database | PostgreSQL + pgvector on Supabase | Supabase provides managed Postgres with pgvector pre-enabled + auth in one service — no separate DB to provision |
| Embeddings | Voyage AI `voyage-3` | 1024 dimensions, better retrieval quality than text-embedding-3-small for long-form text; Anthropic-owned, one vendor relationship |
| Generation | Claude API (`claude-sonnet-4-20250514`) | Better long-context lore synthesis than GPT-4o; differentiated on resume |
| Auth | Supabase | Gives you Postgres + JWT auth + user table in one service |
| Frontend (Week 3) | Next.js + Tailwind | SSR, streaming support, Vercel deployment |
| Hosting | Vercel (frontend) + Railway (backend) + Supabase (DB + auth) | Free tiers, no AWS config overhead eating your timeline |

---

## Data Model

### Design Principle: Fandom as a First-Class Entity

Every table is scoped to a fandom via `fandom_id`. This is the platform abstraction. Adding LOTR in v3 is a configuration + ingestion task, not a re-architecture.

---

### `fandoms`
```sql
CREATE TABLE fandoms (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        TEXT UNIQUE NOT NULL,  -- 'one-piece', 'lotr', 'bg3'
  name        TEXT NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Seed for v1
INSERT INTO fandoms (slug, name) VALUES ('one-piece', 'One Piece');
```

---

### `arcs`
The spoiler gate backbone. Every chunk references an `arc_index`. The filter is always `arc_index <= user_arc_index`.

```sql
CREATE TABLE arcs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fandom_id   UUID REFERENCES fandoms(id),
  slug        TEXT NOT NULL,        -- 'marineford-arc'
  name        TEXT NOT NULL,        -- 'Marineford Arc'
  saga_name   TEXT NOT NULL,        -- 'Summit War Saga'
  arc_index   INTEGER NOT NULL,     -- global ordering key, e.g. 18
  saga_index  INTEGER NOT NULL,     -- ordering within saga
  UNIQUE(fandom_id, arc_index)
);
```

**One Piece official arc taxonomy to seed (arc_index order):**

| arc_index | Arc Name | Saga |
|---|---|---|
| 1 | Romance Dawn Arc | East Blue Saga |
| 2 | Orange Town Arc | East Blue Saga |
| 3 | Syrup Village Arc | East Blue Saga |
| 4 | Baratie Arc | East Blue Saga |
| 5 | Arlong Park Arc | East Blue Saga |
| 6 | Loguetown Arc | East Blue Saga |
| 7 | Reverse Mountain Arc | Alabasta Saga |
| 8 | Whisky Peak Arc | Alabasta Saga |
| 9 | Little Garden Arc | Alabasta Saga |
| 10 | Drum Island Arc | Alabasta Saga |
| 11 | Alabasta Arc | Alabasta Saga |
| 12 | Jaya Arc | Sky Island Saga |
| 13 | Skypiea Arc | Sky Island Saga |
| 14 | Long Ring Long Land Arc | Water 7 Saga |
| 15 | Water 7 Arc | Water 7 Saga |
| 16 | Enies Lobby Arc | Water 7 Saga |
| 17 | Post-Enies Lobby Arc | Water 7 Saga |
| 18 | Thriller Bark Arc | Summit War Saga |
| 19 | Sabaody Archipelago Arc | Summit War Saga |
| 20 | Amazon Lily Arc | Summit War Saga |
| 21 | Impel Down Arc | Summit War Saga |
| 22 | Marineford Arc | Summit War Saga |
| 23 | Post-War Arc | Summit War Saga |
| 24 | Return to Sabaody Arc | Fish-Man Island Saga |
| 25 | Fish-Man Island Arc | Fish-Man Island Saga |
| 26 | Punk Hazard Arc | Dressrosa Saga |
| 27 | Dressrosa Arc | Dressrosa Saga |
| 28 | Zou Arc | Whole Cake Island Saga |
| 29 | Whole Cake Island Arc | Whole Cake Island Saga |
| 30 | Levely Arc | Wano Country Saga |
| 31 | Wano Country Arc | Wano Country Saga |
| 32 | Egghead Arc | Final Saga |
| 33 | Elbaph Arc | Final Saga |

---

### `pages`
One row per scraped wiki page. Raw HTML stored so you can re-chunk without re-scraping.

```sql
CREATE TABLE pages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fandom_id   UUID REFERENCES fandoms(id),
  page_type   TEXT NOT NULL CHECK (page_type IN (
                'character', 'arc', 'devil_fruit', 'crew', 'concept'
              )),
  title       TEXT NOT NULL,       -- 'Portgas D. Ace'
  url         TEXT UNIQUE NOT NULL,
  raw_html    TEXT,
  scraped_at  TIMESTAMPTZ DEFAULT now()
);
```

---

### `chunks`
The core table. One row per chunk. This is what gets embedded and searched.

```sql
CREATE TABLE chunks (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id           UUID REFERENCES pages(id),
  fandom_id         UUID REFERENCES fandoms(id),
  content           TEXT NOT NULL,
  embedding         vector(1024),
  page_type         TEXT NOT NULL,
  section_title     TEXT,             -- 'Personality', 'Marineford Arc', 'Abilities'
  arc_id            UUID REFERENCES arcs(id),
  arc_index         INTEGER NOT NULL, -- denormalized for fast filter
  spoiler_sensitive BOOLEAN DEFAULT false,
  entity_names      TEXT[],           -- ['Ace', 'Whitebeard', 'Akainu']
  content_type      TEXT CHECK (content_type IN (
                      'character_history', 'arc_summary', 'ability',
                      'quote', 'concept', 'crew', 'devil_fruit'
                    )),
  chunk_index       INTEGER,          -- position within parent page
  token_count       INTEGER,
  created_at        TIMESTAMPTZ DEFAULT now()
);

-- Critical indexes
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON chunks (fandom_id, arc_index);
CREATE INDEX ON chunks (fandom_id, arc_index, spoiler_sensitive);
CREATE INDEX ON chunks USING gin (entity_names);  -- for entity lookups
```

---

### `users`
Not a table you create. Supabase Auth owns `auth.users` — it manages the user record, hashed password, and JWT issuance. Your tables reference it via the user's UUID.

### `user_arc_progress`
One row per user per fandom. The API reads this to scope every query.

```sql
CREATE TABLE user_arc_progress (
  user_id         UUID REFERENCES auth.users(id),
  fandom_id       UUID REFERENCES fandoms(id),
  current_arc_id  UUID REFERENCES arcs(id),
  arc_index       INTEGER NOT NULL,    -- denormalized for fast query
  media_mode      TEXT DEFAULT 'anime' CHECK (media_mode IN ('anime', 'manga')),
  updated_at      TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, fandom_id)
);
```

---

## Week 1: Corpus & Ingestion Pipeline

### Goal
A fully queryable corpus in Postgres with embeddings and accurate metadata by end of week.

### Corpus Scope (v1 — accuracy over completeness)

Start with these page types in priority order. Do not try to ingest everything.

| Priority | Page Type | Why |
|---|---|---|
| 1 | Arc pages | Clean structure, safe to tag, foundation of spoiler taxonomy |
| 2 | Major character pages | Highest query value, requires careful section-level chunking |
| 3 | Devil Fruit pages | High query value, relatively safe, well-structured |
| 4 | Concept pages | Haki, Will of D, Poneglyphs — important but spoiler-sensitive |
| 5 | Crew pages | Supporting context, lower priority |

**Seed URLs (entry points):**
- `https://onepiece.fandom.com/wiki/Story_Arcs` — all arc pages
- `https://onepiece.fandom.com/wiki/Category:Characters` — character page index
- `https://onepiece.fandom.com/wiki/Category:Devil_Fruit` — devil fruit index
- `https://onepiece.fandom.com/wiki/Category:Crews` — crew pages

### Scraper Architecture

```
project/
├── scraper/
│   ├── scrape.py          # Entry point, manages queue + rate limiting
│   ├── fetch.py           # HTTP fetch with headers + retry logic
│   ├── parse.py           # BeautifulSoup parsing, section extraction
│   ├── tag.py             # Arc tagging logic
│   └── store.py           # DB writes for pages table
├── ingestion/
│   ├── chunk.py           # Chunking logic
│   ├── embed.py           # Voyage AI embedding calls
│   └── store_chunks.py    # DB writes for chunks table
├── db/
│   └── schema.sql         # All CREATE TABLE statements
└── config.py              # Arc index map, fandom slugs, constants
```

### Rate Limiting — Non-Negotiable

```python
import time
import random

def polite_fetch(url: str, session: requests.Session) -> requests.Response:
    time.sleep(random.uniform(1.0, 2.5))  # randomized delay
    headers = {
        "User-Agent": "Lorekeeper/1.0 (lorekeeper.app; fan research tool)"
    }
    response = session.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response
```

Never remove the delay. Fandom will rate-limit or block you.

### Parsing: Section Extraction

Fandom wiki content always lives in `div.mw-parser-output`. Extract by `h2`/`h3` headers.

```python
from bs4 import BeautifulSoup, Tag

def extract_sections(soup: BeautifulSoup) -> list[dict]:
    content = soup.find("div", class_="mw-parser-output")
    
    # Remove noise before parsing
    for tag in content.find_all(["table", "sup", "div.navbox"]):
        tag.decompose()
    for tag in content.find_all("span", class_="mw-editsection"):
        tag.decompose()
    
    sections = []
    current_section = {"title": "Overview", "text": "", "level": 2}
    
    for element in content.children:
        if isinstance(element, Tag):
            if element.name in ["h2", "h3"]:
                # Save previous section if it has content
                if current_section["text"].strip():
                    sections.append(current_section)
                current_section = {
                    "title": element.get_text(strip=True).replace("[edit]", ""),
                    "text": "",
                    "level": int(element.name[1])
                }
            else:
                current_section["text"] += element.get_text(separator=" ", strip=True) + " "
    
    # Don't forget last section
    if current_section["text"].strip():
        sections.append(current_section)
    
    return sections
```

### Arc Tagging Logic

This is the most important — and most manual — part of Week 1. Two tagging strategies depending on page type:

**Arc pages:** Tag = the arc itself. Simple.
```python
# For an arc page about Marineford Arc
arc_index = ARC_INDEX_MAP["marineford-arc"]  # 22
```

**Character pages:** Tag each *section* based on its header.
```python
ARC_SECTION_MAP = {
    # Section header text → arc_index
    "romance dawn arc": 1,
    "orange town arc": 2,
    "syrup village arc": 3,
    "baratie arc": 4,
    "arlong park arc": 5,
    "loguetown arc": 6,
    # ... all arcs
    "marineford arc": 22,
    "post-war arc": 23,
    "wano country arc": 31,
    "egghead arc": 32,
}

def tag_section(section_title: str, page_type: str, intro_arc_index: int) -> int:
    normalized = section_title.lower().strip()
    
    # Direct arc name match
    if normalized in ARC_SECTION_MAP:
        return ARC_SECTION_MAP[normalized]
    
    # Non-arc sections (Personality, Abilities, Appearance, Relationships)
    # Tag to the character's introduction arc — conservative
    return intro_arc_index
```

**Spoiler sensitivity rules (apply manually for v1):**
- Any section mentioning a character death → `spoiler_sensitive = True`
- Identity reveal sections → `spoiler_sensitive = True`
- Concept pages covering late-game lore (Void Century, Im, Joy Boy) → `spoiler_sensitive = True`
- Mark these explicitly in a `SPOILER_SENSITIVE_PATTERNS` list you maintain in `config.py`

### Chunking Logic

```python
import tiktoken

CHUNK_SIZE = 450       # target tokens
CHUNK_OVERLAP = 50     # overlap between chunks

encoder = tiktoken.get_encoding("cl100k_base")  # reasonable token counter for chunking; not Voyage-specific but accurate enough

def chunk_section(section_text: str) -> list[str]:
    tokens = encoder.encode(section_text)
    chunks = []
    
    start = 0
    while start < len(tokens):
        end = min(start + CHUNK_SIZE, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(encoder.decode(chunk_tokens))
        
        if end == len(tokens):
            break
        start = end - CHUNK_OVERLAP  # slide back for overlap
    
    return chunks
```

**Hard rules:**
- Never chunk across section boundaries — section boundary = hard split
- Sections under 100 tokens are kept as a single chunk (don't split tiny sections)
- Sections over 1000 tokens get chunked with overlap as above
- Each chunk inherits its section's `arc_index` and `spoiler_sensitive` flag

### Embedding

```python
import voyageai

client = voyageai.Client()  # reads VOYAGE_API_KEY from env

def embed_chunks(chunks: list[str]) -> list[list[float]]:
    # Batch up to 128 chunks per API call
    result = client.embed(chunks, model="voyage-3")
    return result.embeddings
```

Batch your embedding calls — don't call the API once per chunk. You'll hit rate limits and it's slow.

### Week 1 Checklist
- [ ] Schema created in Postgres with pgvector extension enabled
- [ ] `fandoms` and `arcs` tables seeded with One Piece taxonomy
- [ ] Scraper running against arc pages, character pages, devil fruit pages
- [ ] Raw HTML stored in `pages` table
- [ ] Section extraction working correctly (verify manually on 5-10 pages)
- [ ] Arc tagging logic producing correct `arc_index` values
- [ ] `ARC_SECTION_MAP` covers all 33 arcs
- [ ] Spoiler-sensitive chunks flagged
- [ ] Chunks embedded and stored in `chunks` table with all metadata
- [ ] Can run `SELECT COUNT(*) FROM chunks` and get a meaningful number (target: 5,000–15,000 chunks)
- [ ] Can run a raw pgvector similarity query and get back sensible results

---

## Week 2: Retrieval + Generation Layer

### Goal
A FastAPI backend that takes a query + user context, retrieves filtered chunks, and streams a grounded response from Claude.

### API Structure

```
api/
├── main.py              # FastAPI app, route registration
├── routes/
│   ├── query.py         # POST /query — main lore Q&A endpoint
│   ├── auth.py          # POST /auth/register, /auth/login
│   └── progress.py      # PUT /user/progress — update arc progress
├── services/
│   ├── retrieval.py     # Embed query + pgvector search
│   ├── generation.py    # Build prompt + stream Claude response
│   └── auth.py          # JWT logic via Supabase
├── db.py                # Async Postgres connection pool
└── models.py            # Pydantic request/response models
```

### Core Query Endpoint

```python
# routes/query.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from services.retrieval import retrieve_chunks
from services.generation import stream_response
from services.auth import get_current_user

router = APIRouter()

@router.post("/query")
async def query_lorekeeper(
    request: QueryRequest,
    user = Depends(get_current_user)
):
    # Get user's arc progress for this fandom
    arc_index = await get_user_arc_index(user.id, request.fandom_id)
    
    # Retrieve relevant chunks (spoiler-filtered)
    chunks = await retrieve_chunks(
        query=request.query,
        fandom_id=request.fandom_id,
        arc_index=arc_index,
        mode=request.mode  # 'lore' or 'theorycraft'
    )
    
    # Stream Claude response
    return StreamingResponse(
        stream_response(request.query, chunks, mode=request.mode),
        media_type="text/event-stream"
    )
```

### Retrieval Service

```python
# services/retrieval.py
import voyageai
import asyncpg

voyage = voyageai.Client()  # reads VOYAGE_API_KEY from env

async def retrieve_chunks(
    query: str,
    fandom_id: str,
    arc_index: int,
    mode: str = "lore",
    top_k: int = 8
) -> list[dict]:
    
    # 1. Embed the query
    result = voyage.embed([query], model="voyage-3")
    query_embedding = result.embeddings[0]
    
    # 2. Vector search with spoiler gate
    # spoiler_sensitive chunks get 1-arc buffer
    sql = """
        SELECT
            content,
            section_title,
            page_type,
            content_type,
            entity_names,
            arc_index,
            1 - (embedding <=> $1::vector) AS similarity
        FROM chunks
        WHERE fandom_id = $2
          AND arc_index <= $3
          AND (
            spoiler_sensitive = false
            OR arc_index <= $3 - 1
          )
        ORDER BY embedding <=> $1::vector
        LIMIT $4
    """
    
    chunks = await db.fetch(sql, query_embedding, fandom_id, arc_index, top_k)
    return [dict(chunk) for chunk in chunks]
```

### Generation Service

Two distinct system prompts — one per mode.

```python
# services/generation.py
import anthropic

client = anthropic.Anthropic()

LORE_SYSTEM_PROMPT = """You are Lorekeeper, a lore assistant for One Piece fans.
You answer questions using ONLY the context chunks provided. Do not use any knowledge
outside of the provided context. If the context doesn't contain enough information
to answer the question, say so clearly.

For each claim you make, note which source it comes from (the section_title).
Never speculate or infer beyond what the context explicitly states.
Format citations as [Source: {section_title}]."""

THEORYCRAFT_SYSTEM_PROMPT = """You are Lorekeeper in Theory Mode. The user wants to
speculate about what happens next in One Piece. You have been given context chunks
representing everything the user currently knows — treat this as the complete universe
of known facts.

Using ONLY this context as your foundation, reason creatively and speculatively about
how events might unfold. Frame everything as theory, not fact. Use phrases like
"one possibility is...", "based on what we know...", "it's possible that...".

NEVER assert future plot points as true. NEVER reference events beyond the provided context.
You are theorizing with the user, not spoiling them."""

async def stream_response(query: str, chunks: list[dict], mode: str = "lore"):
    system_prompt = LORE_SYSTEM_PROMPT if mode == "lore" else THEORYCRAFT_SYSTEM_PROMPT
    
    context = "\n\n---\n\n".join([
        f"[{c['section_title']} | {c['page_type']}]\n{c['content']}"
        for c in chunks
    ])
    
    user_message = f"""Context:\n{context}\n\nQuestion: {query}"""
    
    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    ) as stream:
        for text in stream.text_stream:
            yield f"data: {text}\n\n"
```

### Auth Layer (Supabase)

```python
# services/auth.py
from supabase import create_client
import os

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

async def register_user(email: str, password: str):
    return supabase.auth.sign_up({"email": email, "password": password})

async def login_user(email: str, password: str):
    return supabase.auth.sign_in_with_password({"email": email, "password": password})

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = supabase.auth.get_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
```

### Arc Progress Endpoint

```python
# routes/progress.py
@router.put("/user/progress")
async def update_arc_progress(
    request: ProgressUpdateRequest,  # { fandom_id, arc_index }
    user = Depends(get_current_user)
):
    await db.execute("""
        INSERT INTO user_arc_progress (user_id, fandom_id, arc_index, updated_at)
        VALUES ($1, $2, $3, now())
        ON CONFLICT (user_id, fandom_id)
        DO UPDATE SET arc_index = $3, updated_at = now()
    """, user.id, request.fandom_id, request.arc_index)
    
    return {"status": "ok"}
```

### Week 2 Checklist
- [ ] FastAPI app scaffolded with route structure above
- [ ] `/query` endpoint returning real answers from retrieved chunks
- [ ] Spoiler gate verified — test with a known spoiler query at an early arc, confirm it does not appear
- [ ] Theorycraft mode prompt working — model speculates without asserting future facts
- [ ] Streaming response working end-to-end (curl test)
- [ ] Auth endpoints working — register, login, JWT returned
- [ ] `/user/progress` endpoint persisting arc progress to DB
- [ ] Citation metadata attached to each response (section_title source)
- [ ] Tested with at least 20 real One Piece queries across different arcs

---

## Environment Variables

```bash
# .env
ANTHROPIC_API_KEY=     # Claude generation
VOYAGE_API_KEY=        # Voyage AI embeddings (Anthropic-owned, separate key)
SUPABASE_URL=
SUPABASE_KEY=
DATABASE_URL=postgresql://...  # Supabase Postgres connection string
FANDOM_SLUG=one-piece
```

---

## Key Design Decisions & Interview Talking Points

**Why pgvector over Pinecone/Weaviate?**
We already use Postgres for user data. pgvector adds vector search as an extension to the same database, avoiding a second managed service, keeping the stack simple, and giving full control over the query — including the metadata filter that powers the spoiler gate. The spoiler gate is a SQL `WHERE` clause, not a prompt instruction. A prompt can be talked around; a metadata filter cannot.

**Why chunk by section rather than by fixed token window?**
A section boundary is a semantic boundary. "Personality" and "Marineford Arc" on Ace's character page are fundamentally different types of information. Mixing them in a single chunk destroys retrieval precision — a query about Ace's personality would surface chunks about his death. Section-aware chunking preserves semantic coherence at the retrieval level.

**Why build retrieval manually instead of using LangChain?**
LangChain abstracts the embed → search → stuff loop into one call. That's convenient but opaque. We own every step: we know exactly how chunking works, why we chose 450 tokens with 50-token overlap, and what the pgvector cosine similarity query looks like. That ownership is what lets you explain the system in an interview with confidence.

**Why `arc_index` denormalized on `chunks`?**
The retrieval query runs on every user request. Joining to the `arcs` table on every query adds latency. Denormalizing `arc_index` onto `chunks` makes the filter a single-table scan with an index — fast and simple.

**Why two separate system prompts for lore vs. theorycraft mode?**
These are fundamentally different epistemic postures. Lore mode: ground every claim in retrieved context, no speculation. Theorycraft mode: use retrieved context as the known universe, reason forward creatively. Combining them in one prompt produces confused output. Keeping them separate makes each mode crisp and testable.
