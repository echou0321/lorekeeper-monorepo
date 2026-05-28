# Lorekeeper — Product Vision & Platform Intent

## What It Is

Lorekeeper is **spoiler-aware lore intelligence infrastructure for knowledge-dense fictional universes.**

It is not a chatbot. It is not a wiki replacement. It is a suite of AI-powered tools — chat, encyclopedia, relationship graph, timeline, theory board — that understands *where you are* in a story and answers accordingly. Every answer is grounded in sourced wiki content, every result filtered to your progress, every speculation contained to what you actually know.

The v1 universe is One Piece. The platform goal is any fandom.

---

## The Core Problem

Every major fandom has the same unsolved problem: **there is no safe, intelligent way to explore lore mid-series.**

- Wikis are spoiler minefields
- Reddit discussions assume full knowledge
- AI chatbots (including Claude, GPT-4) have no concept of where you are in the story
- Fan forums require knowing what to search for

A new One Piece fan on episode 400 has no tool that says: *"here is everything you can safely know right now, and here is what the community thinks happens next."* Lorekeeper is that tool.

---

## The Killer Feature: Spoiler-Gated Retrieval

Every query runs through a spoiler gate. The user declares the last arc they **fully completed**. The system filters its entire corpus to content tagged at or before that arc. Nothing leaks.

This is not a UI toggle. It is a hard constraint built into the retrieval layer — `arc_index <= user_arc_index` — enforced at the database query level, not in the prompt. A prompt instruction can be talked around. A metadata filter cannot.

Edge cases (reveals that don't map cleanly to arc boundaries) are handled via a `spoiler_sensitive` flag that adds an extra arc buffer.

---

## Feature Roadmap

### v1 — One Piece (Weeks 1–4)
- Spoiler-gated lore Q&A with source citations
- Arc selector onboarding (official One Piece saga/arc taxonomy)
- "Explain this to me like I just finished X arc" mode
- Theorycraft mode (speculative, spoiler-safe, model reasons forward from user's knowledge base)
- Recommended follow-up questions
- Basic auth with persistent arc progress per user
- Devil Fruit / Haki encyclopedia (filterable, spoiler-gated)
- Live deployed URL (Vercel + Railway)

### v1.5 — Depth (Month 2)
- Quote finder ("find the scene where Whitebeard says the One Piece is real")
- Character relationship mapper — visual graph of named entity connections
- Knowledge profile — visual map of unlocked lore, arc completion progress
- Chapter drop integration — re-ingestion pipeline on new manga releases, "New lore unlocked" notifications
- Anime vs. manga mode toggle (anime-only users protected from manga-first content)
- Reread companion mode — spoiler gate off, answers annotated with foreshadowing

### v2 — Social Layer (Month 3+)
- Theory board — users post theories tagged by arc, others at the same arc can engage
- Theory aging — posted theories auto-marked Confirmed / Debunked / Still Open as corpus updates
- Arc completion celebrations — recap of community theories from that arc, shareable
- Spoiler-safe discussion rooms — gated by arc completion, no cross-contamination
- Reading / watch journal logs

### v3 — Platform Expansion
- Multi-fandom support (LOTR, BG3, Elden Ring, House of the Dragon, Wheel of Time, Dune)
- Fandom as a first-class data entity — every chunk, every user arc, every spoiler taxonomy scoped to a fandom
- Onboarding a new fandom = define arc taxonomy + run ingestion pipeline. Zero re-architecture.
- Embed widget for fan sites ("Powered by Lorekeeper")
- Streamer mode — minimal UI, fast answers, zero spoilers for live reaction content
- Creator / wiki community partnerships for cleaner data ingestion

---

## Platform Architecture Principle

The most important architectural decision for the platform goal is made in Week 1: **Fandom is a first-class entity in the data model.**

Every corpus chunk belongs to a fandom. Every user has arc progress *per fandom*. Every spoiler taxonomy is fandom-specific. Every query is scoped to a fandom.

This means adding LOTR in v3 is:
1. Define the arc taxonomy for LOTR
2. Run the ingestion pipeline against the LOTR wiki
3. Done

It is a configuration and operations task, not an engineering task. That is the platform.

---

## Positioning

> *"The only lore tool that knows where you are in the story."*

**For casual fans:** Safe answers to questions you're afraid to Google.
**For mid-series readers:** Theorycraft with an AI that only knows what you know.
**For veteran fans:** Reread companion with foreshadowing annotations and community theory history.
**For the platform:** Any fandom, same infrastructure, one arc selector away.

---

## Monetization (Future)
- Free tier: limited queries per day, One Piece only
- Pro tier: unlimited queries, all fandoms, theory board, knowledge profile
- Supporter badges: cosmetic perks on the theory board for contributors
