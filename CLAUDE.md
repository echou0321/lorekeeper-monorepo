# Lorekeeper — Claude Code Context

## What This Project Is

Lorekeeper is a spoiler-aware lore intelligence platform for knowledge-dense fictional universes. V1 is One Piece. The long-term goal is a multi-fandom platform where onboarding a new fandom (LOTR, BG3, Elden Ring) is a configuration and ingestion task, not an engineering task.

The killer feature: every query is filtered by the user's arc progress at the database level (`arc_index <= user_arc_index`). This is not a prompt instruction — it is a hard metadata filter in the pgvector query. A prompt can be talked around; a SQL WHERE clause cannot.

## Monorepo Structure

```
lorekeeper/
├── api/          # FastAPI backend — persistent server, deployed on Railway
├── ingestion/    # One-time automation scripts — scrape, chunk, embed, store
├── db/           # schema.sql — run once on Supabase Postgres
├── web/          # Next.js frontend — deployed on Vercel (Week 3, placeholder for now)
└── docs/         # Design docs for reference
```

`api/` and `ingestion/` are both Python but intentionally separate. Different dependencies, different entry points, different deployment targets. Do not mix them.

## Stack

| Layer | Technology |
|---|---|
| Scraping | Python + BeautifulSoup |
| Backend API | FastAPI (Python) |
| Database | PostgreSQL + pgvector on Supabase |
| Embeddings | Voyage AI `voyage-3` (1024 dimensions) |
| Generation | Anthropic Claude `claude-sonnet-4-20250514` |
| Auth | Supabase Auth (JWT issued by Supabase, validated in FastAPI) |
| Frontend | Next.js + Tailwind (Week 3) |
| API Hosting | Railway |
| Frontend Hosting | Vercel |

**Hosting split:** Supabase handles Postgres + pgvector + auth in one service. Railway runs the FastAPI backend only. This is the right call for a solo build — auth is not the interesting engineering problem here; the spoiler gate, chunking strategy, and retrieval pipeline are.

## Key Constants

```python
FANDOM_SLUG = "one-piece"
EMBEDDING_MODEL = "voyage-3"
EMBEDDING_DIMENSIONS = 1024
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CHUNK_SIZE = 450        # tokens
CHUNK_OVERLAP = 50      # tokens
TOP_K_CHUNKS = 8        # chunks retrieved per query
```

## Spoiler Gate Logic

Every chunk in the database has an `arc_index` integer — its position in the official One Piece arc taxonomy (1 = Romance Dawn, 33 = Elbaph). Users declare the last arc they fully completed. The retrieval query filters strictly:

```sql
WHERE arc_index <= user_arc_index
  AND (spoiler_sensitive = false OR arc_index <= user_arc_index - 1)
```

`spoiler_sensitive = true` chunks (identity reveals, deaths, late-game concept explanations) get a 1-arc buffer on top of the base filter.

## Two Query Modes

**Lore mode** — ground every claim in retrieved context only, cite sources, no speculation.
**Theorycraft mode** — use retrieved context as the known universe, reason forward creatively, never assert future facts as true.

These use separate system prompts. Do not combine them.

## Data Model (key tables)

- `fandoms` — platform abstraction, every row scoped by fandom_id
- `arcs` — official arc taxonomy, arc_index is the spoiler gate key
- `pages` — one row per scraped wiki page, raw HTML stored for re-chunking
- `chunks` — core table, one row per chunk with embedding + all metadata
- `users` — managed by Supabase Auth; user UUID is the foreign key in all other tables
- `user_arc_progress` — one row per user per fandom, stores arc_index

## Ingestion Pipeline Order

```
run_pipeline.py
  → scraper/scrape.py      # fetch wiki pages, store raw HTML in pages table
  → chunk.py               # extract sections, chunk by section boundary
  → embed.py               # batch embed chunks via Voyage AI
  → store.py               # write chunks + embeddings to DB
```

Re-run pipeline when wiki content updates (chapter drops). Raw HTML stored in `pages` table so re-chunking doesn't require re-scraping.

## Chunking Rules

- Never chunk across section boundaries — hard split at every h2/h3
- Target 450 tokens per chunk, 50-token overlap
- Sections under 100 tokens kept as single chunk
- Each chunk inherits its section's arc_index and spoiler_sensitive flag
- Character page arc history sections tagged to their matching arc_index
- Non-arc sections (Personality, Abilities, Appearance) tagged to character's introduction arc

## API Endpoints

- `POST /query` — main lore Q&A, requires auth, streams Claude response
- `POST /auth/register` — delegates to Supabase Auth sign-up
- `POST /auth/login` — delegates to Supabase Auth, returns Supabase JWT
- `PUT /user/progress` — update user's arc_index for a fandom

## Environment Variables

```bash
ANTHROPIC_API_KEY=     # Claude generation
VOYAGE_API_KEY=        # Voyage AI embeddings (Anthropic-owned, separate key, one vendor)
SUPABASE_URL=          # from Supabase project settings
SUPABASE_KEY=          # service role key (backend only, never expose to client)
DATABASE_URL=          # Supabase Postgres connection string (for direct psycopg2/asyncpg access)
FANDOM_SLUG=one-piece
```

## Build Progress

### Week 1 — Corpus & Ingestion
- [x] `db/schema.sql` — all tables, indexes, One Piece arc seed data
- [x] Schema applied to Supabase (pgvector enabled, fandoms + arcs verified)
- [x] `ingestion/` pipeline scaffolded — fetch, parse, tag, chunk, embed, store
- [ ] Single test page verified end-to-end (Marineford Arc → chunks in DB)
- [ ] Full scrape across arc, character, devil fruit pages
- [ ] Chunk count target: 5,000–15,000

### Week 2 — API
- [ ] FastAPI app scaffolded
- [ ] `/query` endpoint with spoiler-gated retrieval
- [ ] Auth endpoints (Supabase delegation)
- [ ] `/user/progress` endpoint
- [ ] Streaming verified via curl

### Week 3 — Frontend
- [ ] Next.js app scaffolded
- [ ] Arc selector + query UI
- [ ] Deployed to Vercel

---

## What We Are NOT Doing (yet)

- No LangChain — retrieval pipeline is hand-rolled for full control and interview explainability
- No Pinecone/Weaviate — pgvector on Supabase keeps everything in one database
- No self-managed auth boilerplate — Supabase Auth handles it; focus goes to the retrieval pipeline
- No GCP/Azure — Railway until we have real traffic and a concrete reason to migrate
- No frontend until the API is proven via curl/Postman

## Future Platform Expansion

Adding a new fandom (LOTR, BG3, etc.) should require:
1. Define the arc taxonomy and seed the `arcs` table
2. Define seed URLs for that fandom's wiki
3. Run `run_pipeline.py` with the new fandom slug

Zero re-architecture. This is only possible if every query, every chunk, and every user record is scoped by `fandom_id` — which they are.
