-- Lorekeeper Database Schema
-- Run once on Supabase.
-- auth.users is managed by Supabase Auth. Do not create a users table.

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- ============================================================
-- FANDOMS
-- ============================================================

CREATE TABLE fandoms (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug       TEXT UNIQUE NOT NULL,  -- 'one-piece', 'lotr', 'bg3'
  name       TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO fandoms (slug, name) VALUES ('one-piece', 'One Piece');


-- ============================================================
-- ARCS
-- arc_index is the spoiler gate key — every chunk carries it,
-- every query filters on it.
-- ============================================================

CREATE TABLE arcs (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fandom_id  UUID NOT NULL REFERENCES fandoms(id),
  slug       TEXT NOT NULL,      -- 'marineford-arc'
  name       TEXT NOT NULL,      -- 'Marineford Arc'
  saga_name  TEXT NOT NULL,      -- 'Summit War Saga'
  arc_index  INTEGER NOT NULL,   -- global ordering key
  saga_index INTEGER NOT NULL,   -- ordering within saga
  UNIQUE (fandom_id, arc_index)
);

-- One Piece arc taxonomy (33 arcs as of Elbaph)
INSERT INTO arcs (fandom_id, slug, name, saga_name, arc_index, saga_index)
SELECT f.id, v.slug, v.name, v.saga_name, v.arc_index, v.saga_index
FROM fandoms f
CROSS JOIN (VALUES
  ('romance-dawn-arc',        'Romance Dawn Arc',        'East Blue Saga',           1,  1),
  ('orange-town-arc',         'Orange Town Arc',         'East Blue Saga',           2,  2),
  ('syrup-village-arc',       'Syrup Village Arc',       'East Blue Saga',           3,  3),
  ('baratie-arc',             'Baratie Arc',             'East Blue Saga',           4,  4),
  ('arlong-park-arc',         'Arlong Park Arc',         'East Blue Saga',           5,  5),
  ('loguetown-arc',           'Loguetown Arc',           'East Blue Saga',           6,  6),
  ('reverse-mountain-arc',    'Reverse Mountain Arc',    'Alabasta Saga',            7,  1),
  ('whisky-peak-arc',         'Whisky Peak Arc',         'Alabasta Saga',            8,  2),
  ('little-garden-arc',       'Little Garden Arc',       'Alabasta Saga',            9,  3),
  ('drum-island-arc',         'Drum Island Arc',         'Alabasta Saga',           10,  4),
  ('alabasta-arc',            'Alabasta Arc',            'Alabasta Saga',           11,  5),
  ('jaya-arc',                'Jaya Arc',                'Sky Island Saga',         12,  1),
  ('skypiea-arc',             'Skypiea Arc',             'Sky Island Saga',         13,  2),
  ('long-ring-long-land-arc', 'Long Ring Long Land Arc', 'Water 7 Saga',            14,  1),
  ('water-7-arc',             'Water 7 Arc',             'Water 7 Saga',            15,  2),
  ('enies-lobby-arc',         'Enies Lobby Arc',         'Water 7 Saga',            16,  3),
  ('post-enies-lobby-arc',    'Post-Enies Lobby Arc',    'Water 7 Saga',            17,  4),
  ('thriller-bark-arc',       'Thriller Bark Arc',       'Summit War Saga',         18,  1),
  ('sabaody-archipelago-arc', 'Sabaody Archipelago Arc', 'Summit War Saga',         19,  2),
  ('amazon-lily-arc',         'Amazon Lily Arc',         'Summit War Saga',         20,  3),
  ('impel-down-arc',          'Impel Down Arc',          'Summit War Saga',         21,  4),
  ('marineford-arc',          'Marineford Arc',          'Summit War Saga',         22,  5),
  ('post-war-arc',            'Post-War Arc',            'Summit War Saga',         23,  6),
  ('return-to-sabaody-arc',   'Return to Sabaody Arc',   'Fish-Man Island Saga',    24,  1),
  ('fish-man-island-arc',     'Fish-Man Island Arc',     'Fish-Man Island Saga',    25,  2),
  ('punk-hazard-arc',         'Punk Hazard Arc',         'Dressrosa Saga',          26,  1),
  ('dressrosa-arc',           'Dressrosa Arc',           'Dressrosa Saga',          27,  2),
  ('zou-arc',                 'Zou Arc',                 'Whole Cake Island Saga',  28,  1),
  ('whole-cake-island-arc',   'Whole Cake Island Arc',   'Whole Cake Island Saga',  29,  2),
  ('levely-arc',              'Levely Arc',              'Wano Country Saga',       30,  1),
  ('wano-country-arc',        'Wano Country Arc',        'Wano Country Saga',       31,  2),
  ('egghead-arc',             'Egghead Arc',             'Final Saga',              32,  1),
  ('elbaph-arc',              'Elbaph Arc',              'Final Saga',              33,  2)
) AS v(slug, name, saga_name, arc_index, saga_index)
WHERE f.slug = 'one-piece';


-- ============================================================
-- PAGES
-- One row per scraped wiki page. Raw HTML stored so re-chunking
-- doesn't require re-scraping.
-- ============================================================

CREATE TABLE pages (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fandom_id  UUID NOT NULL REFERENCES fandoms(id),
  page_type  TEXT NOT NULL CHECK (page_type IN (
               'character', 'arc', 'devil_fruit', 'crew', 'concept'
             )),
  title      TEXT NOT NULL,        -- 'Portgas D. Ace'
  url        TEXT UNIQUE NOT NULL,
  raw_html   TEXT,
  scraped_at TIMESTAMPTZ DEFAULT now()
);


-- ============================================================
-- CHUNKS
-- Core table. One row per chunk. This is what gets embedded
-- and retrieved. arc_index is denormalized here for fast
-- single-table filtering — no join on every query.
-- ============================================================

CREATE TABLE chunks (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id           UUID NOT NULL REFERENCES pages(id),
  fandom_id         UUID NOT NULL REFERENCES fandoms(id),
  content           TEXT NOT NULL,
  embedding         vector(1024),          -- Voyage AI voyage-3
  page_type         TEXT NOT NULL,
  section_title     TEXT,                  -- 'Personality', 'Marineford Arc'
  arc_id            UUID REFERENCES arcs(id),
  arc_index         INTEGER NOT NULL,      -- denormalized from arcs.arc_index
  spoiler_sensitive BOOLEAN DEFAULT false, -- adds 1-arc buffer in retrieval filter
  entity_names      TEXT[],               -- ['Ace', 'Whitebeard', 'Akainu']
  content_type      TEXT CHECK (content_type IN (
                      'character_history', 'arc_summary', 'ability',
                      'quote', 'concept', 'crew', 'devil_fruit'
                    )),
  chunk_index       INTEGER,              -- position within parent page
  token_count       INTEGER,
  created_at        TIMESTAMPTZ DEFAULT now()
);

-- HNSW index for fast approximate nearest-neighbor vector search
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
-- Composite index covering the spoiler gate filter on every query
CREATE INDEX ON chunks (fandom_id, arc_index);
CREATE INDEX ON chunks (fandom_id, arc_index, spoiler_sensitive);
-- GIN index for entity name lookups
CREATE INDEX ON chunks USING gin (entity_names);


-- ============================================================
-- USER ARC PROGRESS
-- One row per user per fandom. Drives the spoiler gate.
-- user_id references auth.users managed by Supabase Auth.
-- ============================================================

CREATE TABLE user_arc_progress (
  user_id        UUID REFERENCES auth.users(id),
  fandom_id      UUID NOT NULL REFERENCES fandoms(id),
  current_arc_id UUID REFERENCES arcs(id),
  arc_index      INTEGER NOT NULL,   -- denormalized for fast query-time filter
  media_mode     TEXT DEFAULT 'anime' CHECK (media_mode IN ('anime', 'manga')),
  updated_at     TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (user_id, fandom_id)
);
