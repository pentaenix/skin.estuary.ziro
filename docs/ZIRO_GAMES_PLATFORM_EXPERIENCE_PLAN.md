# Platform Experience Plan

Design plan for giving each console a real presence in Ziro Games — not just as a filter on ROM files, but as something the user recognizes, browses, and enjoys the way they browse a movie studio or genre in Estuary.

This document is intentionally **product- and experience-focused**. It does not prescribe databases, APIs, or file layouts. Those belong in a later technical spec once import, home rows, and game metadata are stable.

## Why this matters

Today a platform is mainly a label the user picks when adding a folder. That solves import and emulator routing, but it does not yet make the living-room experience feel complete.

The north star remains unchanged: **Games should feel like Movies.** Movies are not only posters in a row — the library also understands what a category *is*. Platforms deserve the same respect: Wii is not just “files ending in `.iso` in this folder.” It is a place in the user’s mental model of their collection.

Platform experience is the layer that answers:

- What consoles do I actually have games for?
- What does each one look and feel like in my library?
- How do I browse one console without wading through unrelated systems?

## What belongs to a platform (vs a game)

Keep the boundary clean so game scraping and platform enrichment do not blur together later.

### Platform owns

- Console identity: name, manufacturer, generation/era
- Library presentation: logo, hero image, optional background art
- Short and long descriptions written for browsing, not for a Wikipedia article
- Optional trailer or preview clip when available and appropriate
- High-level facts that help orientation: release era, media type (cartridge, disc, digital), typical input style if useful for context
- “This is part of my collection” signals: game count, recently played on this system, last scan health

### Game owns

- Individual title, cover, synopsis, release year, developer, genre tags
- Play history, favorites, launch action
- ROM-specific details the user should never need to see in normal browsing

**Rule of thumb:** if it describes the *machine or the shelf*, it is platform content. If it describes the *title you play*, it is game content.

## Target user moments

### 1. Games home — platform rows feel intentional

When the user highlights **Games** on the Kodi home screen, platform rows should read as curated shelves, not anonymous lists.

```text
Games
  Continue Playing
  Recently Added
  Favorites
  Nintendo Wii          ← row feels like “my Wii shelf”
  PlayStation 2
  Game Boy Advance
```

Each row should feel anchored to that console’s identity: label, optional small logo, and artwork tone consistent with Estuary — subtle, not flashy.

**Default behavior:** selecting a game in the row still launches play. Platform browsing is available, but must not block the one-click play path.

### 2. Platform browse — a console as a destination

The user should be able to enter a platform view that feels like opening a section of the library:

- Hero or fanart backdrop in Estuary’s language
- Console name and short tagline
- Grid or shelf of games on that system
- Sensible sort options: alphabetical, recently added, recently played, favorites

This is the main “I want everything on my Wii” surface. It should not feel like a settings screen or a file browser.

### 3. Platform info — optional depth, never required

Some users will want more context. Offer a **platform info** moment similar in spirit to movie info — not a mandatory stop on the way to play.

Possible content, richest first:

- Short description (2–4 sentences)
- Representative artwork
- Optional trailer / preview
- Light facts: manufacturer, era, media format
- Collection summary: number of games, last played title, date library was last refreshed

**Tone:** living-room friendly. Interesting enough to browse on a couch, not encyclopedic.

### 4. Setup and empty states — platforms help, not lecture

When a user adds their first source for a console, the UI can acknowledge the platform warmly:

```text
Nintendo Wii source added
Add more games anytime. Scan your library to fill this shelf.
```

When a platform has a source but zero matched games, show platform-aware guidance (“No Wii games found in this folder yet”) rather than generic errors.

When a platform has no source at all, home rows for that system should simply not appear — the library reflects what the user actually collects.

## Content and quality principles

1. **Estuary first.** Platform art and layouts should match Movies/TV: spacing, typography, restrained use of fanart, no custom “game launcher” aesthetic.
2. **Earned presence.** Platforms appear in the UI because the user has (or is setting up) content for them — not because we ship a static grid of every console ever made.
3. **Art over text.** A good logo and hero image do more than paragraphs. Description and trailer are supporting material.
4. **Trailers are optional delight.** Nice when available; never required for a usable shelf. Silent fallback to art + copy.
5. **Respect manual curation.** If the user overrides a platform image or description, rescans and background updates should not stomp their choices without intent.
6. **Offline-tolerant.** Cached artwork should survive everyday use. Network calls are for enrichment, not for simply opening a shelf.
7. **Do not compete with game covers.** Platform art sets context; game covers remain the stars in the row.

## Relationship to other work

This plan sits **after** the core library loop is trustworthy:

| Prerequisite | Why it comes first |
|--------------|-------------------|
| Source import with explicit console selection | Platform identity must be stable before we decorate it |
| Game scan and listing | Empty platform shells are not compelling |
| Home row integration | Platform shelves need a surface to live on |
| Game artwork / metadata | Game covers and platform identity are complementary, not interchangeable |

Platform enrichment should **reuse the same metadata providers** the game library will use, but as a separate concern: console/system artwork and facts, not per-title matching.

## Phased rollout (product phases)

### Phase A — Identity in the UI (minimum lovable)

- Platform rows and browse views use name + default/fallback console artwork
- Row headers and platform browse feel distinct from generic game lists
- Collection counts and “last played on this system” visible where natural

**Done when:** the user can tell which console each shelf belongs to without reading file extensions.

### Phase B — Enriched platform pages

- Short descriptions for supported platforms
- Logo, hero, and background art from curated or scraped sources
- Platform info screen with artwork and summary

**Done when:** opening a platform feels closer to opening a genre hub in Estuary than to a file index.

### Phase C — Motion and polish

- Optional trailers or preview clips on platform info
- Subtle transitions or backdrop behavior consistent with Estuary info dialogs
- Strongest art for platforms the user actively collects

**Done when:** the experience feels intentional and premium, not merely functional.

### Phase D — Full library character (stretch)

- Richer historical/contextual copy where it adds charm
- Deeper facts for enthusiasts who open platform info
- Possible cross-links: “more games like those on this system” using genres or play patterns

**Done when:** long-term collectors enjoy browsing platforms for their own sake, not only to launch a title.

## Out of scope for this plan

- Replacing game-level metadata or scraping
- Emulator configuration UI dressed up as platform pages
- Showing platforms the user does not own games for, “for discovery”
- Store/marketplace integration or buying games
- Achievement lists, BIOS management, or technical emulator setup
- Custom skins or non-Estuary visual languages

## Open design questions (resolve during implementation)

These are deliberately left open so architecture can evolve:

- Should platform info live in a dialog, a full view, or a side panel — whichever matches Estuary patterns best at implementation time?
- Do we show a platform row on home when a source exists but scanning has not run yet?
- How much manufacturer grouping matters (“Nintendo” parent shelf vs individual console rows only)?
- Are trailers autoplay muted on the info screen, or explicit play only?
- Should platform artwork age with theme/color settings, or always use full-color logos?

Document answers when chosen; do not guess them in advance.

## Success criteria

Platform experience is successful when a non-technical user on the TV PC can say:

1. “I can see my Wii / PS2 / GBA shelves clearly on the Games home screen.”
2. “I know what each shelf is without guessing from filenames.”
3. “I can browse one console without seeing games from another.”
4. “I can still pick a game and play in one click.”
5. “Optional info and trailers are nice extras — I never needed them just to play.”

## Related documents

- `ZIRO_GAMES_HOME_WIDGET_PLAN.md` — where platform rows first appear on the home screen
- `ZIRO_GAMES_DYNAMIC_LIBRARY_SPEC.md` — platform and source data model (technical)
- `ZIRO_GAMES_ARCHITECTURE.md` — overall add-on split and responsibilities
- `CODEX_HANDOFF.md` — product north star and milestone order
