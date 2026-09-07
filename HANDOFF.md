# Handoff — Penn Unified Events Calendar

Status as of **2026-09-07** (updated same day to add Athletics), git HEAD `f94f03b`.
Read the "Uncommitted work" section first — a real amount of what's described below
is not yet in git history.

## What this project is

A unified events calendar for Penn, built in three pieces:

1. **Ingestion backend** (`penn_events/`) — Python/Postgres. Feeders pull events from
   Penn's ~511 individual calendars (catalogued in `penn-calendars.csv` /
   `calendar_source_types.md`), normalize them, and write to two tables:
   `calendars` (the source registry, mirrors the CSV) and `events` (the unified
   store). Architecture: `master.yaml` → `FeederFactory` → `Feeder.fetch()` →
   `Adapter.adapt()` → `Normalizer`/`Tagger` → `EventRepository.upsert_many()`.
2. **PostgREST API** (`docker-compose.yml`'s `postgrest` service + `alembic/versions/
   0002_api_schema.py`, `0003_events_school_division.py`) — a read-only, auto-generated
   REST API over a dedicated `api.events` view. No hand-written API server.
3. **Frontend** (`upennevents-fe/`) — React + TypeScript + Vite, calendar (Month/Week)
   and List views, talks to PostgREST directly. Not yet deployed anywhere.

Full original architecture rationale lives in the Claude Code plan file at
`~/.claude/plans/read-calendar-source-types-md-and-penn-c-elegant-reef.md` on this
machine (not part of the repo) — this doc is the portable summary.

---

## Uncommitted work — read this before doing anything else

`git status` currently shows these as modified/untracked against HEAD, despite
HEAD's own commit message ("feat: added ingestion for SP2, Dental, Design, SAS and
GSE") suggesting they'd be included — they are not. **Verify and commit (or
otherwise reconcile) before trusting `git log` as the source of truth**:

```
 M docker-compose.yml                       (PGRST_DB_MAX_ROWS 200 -> 2000)
 M penn_events/adapters/jsonld_adapter.py   (accepts any `*Event` schema.org type, not just "Event")
 M penn_events/cli.py                       (validate-config now hard-fails)
 M penn_events/config/master.yaml           (5 new html/rss/tec feeders + athletics generator + updated notes)
 M penn_events/feeders/__init__.py          (registers the new rss feeder)
 M penn_events/normalize/datetimes.py       (Unix-epoch-string parsing fix)
 M penn_events/pipeline/runner.py           (registry_url now hard-fails, not warns)
 M tests/test_normalize/test_datetimes.py   (test for the epoch fix)
?? alembic/versions/0003_events_school_division.py
?? penn_events/adapters/rss_adapter.py
?? penn_events/feeders/rss.py
?? tests/fixtures/html_sample.html
?? tests/fixtures/jsonld_sample.html
?? tests/fixtures/jsonld_sidearm_sample.html
?? tests/fixtures/rss_sample.xml
?? tests/test_adapters/test_html_adapter.py
?? tests/test_adapters/test_jsonld_adapter.py
?? tests/test_adapters/test_rss_adapter.py
?? upennevents-fe/                          (entire frontend, never committed)
```

---

## What's implemented and verified

### Backend schema & PostgREST API (committed, migrations `0001`–`0003` applied)
- Two tables (`calendars`, `events`) per the original architecture plan.
- `api.events` — a read-only view (schema `api`, role `web_anon`) exposing events
  minus internal columns (`raw`, `dedupe_key`, `content_hash`, `source_uid`,
  `status`), joined to `calendars.school_division` so the frontend can show a real
  school taxonomy instead of guessing from tags. `docker-compose.yml`'s `postgrest`
  service serves it on `localhost:3001`. `PGRST_DB_MAX_ROWS` is `2000` (was `200` —
  raised this session after real data crossed that ceiling and the List view started
  silently truncating results).

### Feeder architecture (all of it already existed before this session)
Four feeder types were already fully implemented and registered before this
session's work: `ics`, `tec_rest`, `jsonld`, `html_css` (see `penn_events/feeders/`,
`penn_events/adapters/`). This session added a fifth:
- **`rss`** (`penn_events/feeders/rss.py`, `penn_events/adapters/rss_adapter.py`) —
  needed because SAS's real feed is RSS with an embedded `<sdo:Event>` schema.org
  block per item (real `startDate`/`endDate`, preferred over `<pubDate>`, which is
  only the item's publish date).

Athletics turned out **not** to need a sixth feeder type. SIDEARM's schedule pages
(`pennathletics.com/sports/<slug>/schedule`) embed a bare JSON-LD array of
`@type: "SportsEvent"` blocks — confirmed live across football, wrestling,
volleyball, crew, and cross country, same shape every time. `SportsEvent` is a
schema.org subtype of `Event`, so the fix was widening
`jsonld_adapter._iter_event_nodes` to accept any `*Event`-suffixed type instead of
requiring an exact `"event"` match, not writing a new adapter. All 31 team-slug
`registry_url`s were taken directly from the `calendars` table (not guessed) and
match `master.yaml`'s new `athletics-teams` generator block exactly.

### Quality fixes made this session
- **`jsonld_adapter` and `html_adapter` test coverage** — previously zero, despite
  being real code. Added fixtures + tests (`tests/fixtures/jsonld_sample.html`,
  `html_sample.html`, matching `tests/test_adapters/test_jsonld_adapter.py`,
  `test_html_adapter.py`).
- **Unix-epoch datetime bug** (`penn_events/normalize/datetimes.py`) — Drupal sites
  commonly render `<time datetime="1788998400">` (a raw epoch string). `dateutil`
  was reading the 10-digit number as a *year*, raising, and silently dropping the
  event. This would have broken GSE ingestion completely, invisibly. Fixed + tested.
- **Silent misconfiguration → loud failure**: previously, a `registry_url` in
  `master.yaml` with no matching `calendars` row just logged a warning and produced
  events with `calendar_id = NULL` (and therefore no `school_division`) — the exact
  bug class that caused the frontend's school filter to look broken earlier in this
  project. `pipeline/runner.py::build_context` now raises `ConfigError` instead
  (caught per-feeder, so one bad config doesn't sink a whole `run-all`); `cli.py
  validate-config` now exits 1 instead of just printing a yellow warning. Verified
  live with a deliberately-broken feeder entry (see commit-pending diff).

### Feeder coverage — 40 feeders wired (9 school feeders + 31 athletics teams), all verified live
Confirmed working via `docker compose run --rm worker python -m penn_events.cli run
<id>` (and a full `run-all`), re-run to confirm idempotence (no duplicate inserts),
and cross-checked `school_division` via the `api.events` join:

| feeder id | type | school_division | events |
|---|---|---|---|
| vpul-university-life | ics | University Life | 64 |
| engineering-tec | tec_rest | Engineering | 67 |
| vet-tec | tec_rest | Vet | 17 |
| faculty-senate-tec | tec_rest | University | 0 (feed currently empty) |
| sas-rss | rss (new) | SAS | 14 |
| gse-html | html_css | GSE | 10 |
| dental-html | html_css | Dental | 17 |
| design-html | html_css | Design | 9 |
| sp2-html | html_css | SP2 | 10 |
| `athletics-teams` generator × 31 slugs | jsonld | Athletics | 579 (sum across all 31 teams) |

**787 active events total**, all with a real `school_division` via
`calendars.school_division`. The 31 athletics feeder ids are `athletics-<slug>`,
e.g. `athletics-football`, `athletics-womens-volleyball` — see `master.yaml`'s
`generators:` block for the full slug list, taken directly from the `calendars`
registry rows (not guessed).

### Frontend (`upennevents-fe/`, never committed, not deployed)
Vite + React + TypeScript. `/calendar` (Month/Week, hand-built to match an approved
design mockup pixel-for-pixel — not a calendar library) and `/list` (search, school
filter, date-range, sort, tag chips). Talks to PostgREST via `VITE_POSTGREST_URL`
(`.env.example`, defaults to `http://localhost:3001`). Category/color taxonomy in
`src/lib/category.ts` mirrors the real 12 Penn schools + Athletics/Student
Life/University-Wide/Other, driven by `event.school_division` from the API — not
guessed from tags (an earlier version did that and was wrong; fixed then reverified
against this session's newly-added schools). `vercel.json` has the SPA rewrite
Vercel needs. Verified with a real build + Playwright click-through against the live
API, screenshots checked.

---

## What remains

Ordered roughly by how the approved plan sequenced it (Step numbers refer to that
plan; see the plan file path above for full detail per item).

### Done: Athletics
No longer on the remaining list — see "Feeder architecture" and "Feeder coverage"
above. Turned out to need zero new feeder/adapter *modules*, just a widened type
filter in `jsonld_adapter.py` plus one `generators:` block in `master.yaml`.

### Blocked, deferred, reasons documented in `master.yaml`'s comments
- **Penn Today** — Cloudflare interstitial to a plain client.
- **Annenberg** (`www.asc.upenn.edu`) — Cloudflare specifically challenges our
  `PennEventsBot` UA (and a Chrome UA) with a 403, while a plain `curl` UA gets a
  real 200. This is deliberate bot-blocking — **do not spoof a browser UA to get
  past it**; needs the same Cloudflare-aware-fetch/Playwright work as Penn Today.
- **Wharton** (`www.wharton.upenn.edu/events/`) — confirmed via view-source it's a
  Salesforce "EventsHQ" widget (`wharton.my.salesforce-sites.com/wevents/...`)
  rendered entirely client-side. No server-rendered content or feed to scrape.
- **Medicine, Law, Nursing** (all LiveWhale) — the real `.ics` subscribe URL is
  generated client-side by the Subscribe button's JS. Tried a scripted Playwright
  click on PSOM's page; it didn't surface a visible link or a new network request
  matching common feed patterns. **Needs more investigation** — likely manual
  browser devtools inspection of the actual XHR/fetch the Subscribe button fires,
  not another scripted attempt. Once one of the three is solved, the other two are
  the same fix (same platform). Law and Nursing also redirect-loop on bare
  `/calendar/` — use `/calendar/view/all`.
- **Almanac** (`https://almanac.upenn.edu/at-penn-calendar`) — loads fine but events
  are inside nested Bootstrap accordion panels, not a flat teaser list. Needs
  selectors hand-tuned against the real panel structure.

### Not started: the other ~450 registry rows (Step 5 of the plan, explicitly low-priority)
Nothing currently visible in the UI is missing beyond the items above, so this is
"finish the whole registry" taken literally, not urgent. It's a repeatable
**probe → classify → config** loop using feeder types that already exist (`html_css`/
`ics`/`tec_rest`/`jsonld`/`rss`), not new code:
1. `cli.py probe <url>` across registry rows not yet in `master.yaml`, batched by
   `platform_cms` (Drupal ~157, WordPress ~145 first — highest yield).
2. Hand-verify selectors per distinct site template (many Drupal sites share a
   theme, so one selector set often covers several rows).
3. Long tail (~12 rows: Trumba, LibCal, Squarespace, CampusGroups, Joomla, iModules,
   Digital Commons) — bespoke small feeders only if/when prioritized.
4. JS-rendered/login-gated sources (Slate admissions portal, DRIA rec portal,
   `groups.wharton.upenn.edu` CampusGroups SPA) deferred to a Playwright feeder.
5. Respect known constraints: skip `www.sas.upenn.edu/departments` and `/centers`
   (robots.txt disallow) and `pan-school.sas.upenn.edu` entirely; treat
   `*.seas.upenn.edu` as `*.engineering.upenn.edu`; ~10 registry rows live on
   non-`upenn.edu` domains (`orphandiseasecenter.org`, `pennlivearts.org`, etc.) and
   need explicit config since a `*.upenn.edu`-scoped crawl would never reach them;
   skip the 43 rows already marked "no dedicated calendar".

### Scheduler — not verified this session
`docker compose logs worker` (as of the start of this session) showed all feeders
scheduled on a 6-hour cron (`0 */6 * * *`), but every event in the DB has
`first_seen_at`/`last_seen_at` from manual `cli run`/`run-all` invocations, not a
real cron tick — an earlier session's log showed a missed 00:00 UTC tick, most
likely because the local Docker host was asleep at that moment. Not re-checked after
this session's changes. Worth confirming a real scheduled run actually fires and
writes data before considering the worker "production-ready," even for local dev.

### Frontend deployment
`upennevents-fe/` is a working local build but was never deployed to Vercel, and
even once deployed it needs PostgREST reachable over the public internet — Vercel
can't host the long-running `postgrest` container itself. This needs a real
deployment target for PostgREST (small VPS, Fly.io, Render, etc.) before the
frontend is useful to anyone but a local developer. `POSTGREST_AUTHENTICATOR_PASSWORD`
is currently a checked-in dev placeholder (`postgrest_dev_password` in
`.env.example`) — must be rotated for any real deployment.

---

## Quick verification commands

```bash
# Bring the stack up (rebuild worker first if you've pulled code changes)
docker compose build worker
docker compose up -d db && docker compose run --rm migrate && docker compose up -d postgrest

# Confirm current DB state
docker compose exec db psql -U penn -d pennevents -c \
  "SELECT c.school_division, count(*) FROM events e JOIN calendars c ON c.id = e.calendar_id WHERE e.status='active' GROUP BY 1 ORDER BY 2 DESC;"

# Run the full ingestion test suite (no network, no DB required)
source .venv/bin/activate && python -m pytest tests/ -q

# Validate master.yaml against the live registry (now hard-fails on a bad registry_url)
docker compose run --rm --entrypoint python worker -m penn_events.cli validate-config

# Re-run every wired feeder (school feeders + generated athletics feeders)
docker compose run --rm --entrypoint python worker -m penn_events.cli run-all

# Frontend dev server (needs postgrest up first)
cd upennevents-fe && cp .env.example .env.local && npm install && npm run dev
```
