# Ingestion status

Snapshot as of **2026-09-07**. This is a point-in-time record of what's wired,
what's deliberately skipped, and what's still open — not a substitute for
`penn_events/config/master.yaml`, which is the operational source of truth and
carries the live reasoning/citations behind every decision below.

## Headline numbers

| | |
|---|---|
| Registry rows (`docs/penn-calendars.csv` → `calendars` table) | 511 |
| Feeders configured in `master.yaml` | 68 (33 explicit + 1 generator expanding to 31 Athletics feeds) |
| Feeders currently yielding events | 66 (2 configured feeders return 0 events right now — see below) |
| Active events in the database | 2,251 |
| Removed events (upstream deleted, kept as history) | 238 |
| School/unit divisions represented | 19 |
| Feeder types in use | `ics`, `tec_rest`, `jsonld`, `rss`, `html_css`, `playwright_html`, `almanac_calendar` |

## Events by school/division (active only)

| Division | Events |
|---|---:|
| Athletics | 579 |
| Medicine | 436 |
| University | 346 |
| Law | 218 |
| Wharton | 205 |
| Engineering | 90 |
| SAS | 65 |
| University Life | 64 |
| Nursing | 57 |
| Alumni | 52 |
| Provost | 32 |
| Penn Global | 26 |
| Vet | 17 |
| Dental | 17 |
| GSE | 10 |
| SP2 | 10 |
| Annenberg | 10 |
| Design | 9 |
| Libraries | 8 |

## Deployment

Production runs on free tiers, with no always-on container:

| Piece | Where it runs |
|---|---|
| Postgres + REST API | Supabase (its API *is* PostgREST, so `api.events` carries over unchanged) |
| Scheduled scrape | GitHub Actions, `.github/workflows/scrape.yml`, every 6 hours |
| Schema migrations | GitHub Actions, `.github/workflows/migrate.yml`, manual dispatch only |
| Frontend | Vercel (static Vite build) |
| Local development | `docker-compose.yml` — not used in production |

The scrape is a batch job (~5 minutes, 4×/day), not a service, so it runs as CI
rather than as a container. Free container tiers spin down when idle, which would
silently stop an in-container scheduler from ever firing.

**Two things to know before touching the database:**

1. **`DB_TARGET` must be `supabase`** when migrating the hosted database. Supabase
   owns the `authenticator` and `anon` roles, and migration `0002` would otherwise
   rewrite `authenticator`'s password and take the hosted API offline. The migration
   detects a managed cluster and aborts with an explanatory error rather than guess,
   so the failure mode is loud — see `penn_events/db/deploy_target.py`.
2. **Two independent controls keep internal columns private.** Supabase must expose
   only the `api` schema (Settings → API → Exposed schemas), *and* `0004` enables
   deny-by-default RLS on `public.events`/`public.calendars`. Either alone would do
   it; both mean a dashboard misconfiguration isn't a data leak. This is also what
   makes it safe for the frontend to ship the Supabase anon key.

`DATABASE_URL` must use Supabase's **session-mode pooler** — GitHub Actions runners
are IPv4-only and Supabase's direct connection is IPv6-only.

### First-time setup

The code is deployment-ready; these steps are the manual half.

1. **Supabase** — create the project. Copy the *session-mode pooler* connection
   string and keep the `postgresql+psycopg://` scheme the code expects.
2. **Settings → API → Exposed schemas** — set to `api`, removing `public`.
3. **GitHub → Settings → Secrets → Actions** — add `DATABASE_URL` (the pooler
   string from step 1). Both workflows read it from there.
4. **Run the `migrate` workflow** manually, with `import_registry` checked. This
   applies the schema and loads all 511 registry rows; the first scrape needs them
   or every event lands without a `school_division`.
5. **Run the `scrape` workflow** manually once to confirm it works, then let the
   6-hourly schedule take over. Confirm one *scheduled* run actually fires —
   a manual dispatch can't tell you whether the cron is healthy.
6. **Vercel** — set `VITE_POSTGREST_URL` to `https://<ref>.supabase.co/rest/v1` and
   `VITE_SUPABASE_ANON_KEY` to the project's anon key, then redeploy. Vite bakes
   these in at build time, so changing them requires a rebuild, not just a restart.

## Architecture recap

`master.yaml` → `FeederFactory` → `Feeder.fetch()` → `Adapter.adapt()` →
normalize/tag → `EventRepository.upsert_many()` → Postgres. Feeders are keyed by
**transport format**, not by school — one class handles every site of a given
shape via YAML-declared config (mainly `html_css`'s per-site CSS selectors).
Seven feeder types cover all 68 wired sources:

| Type | What it covers | Feeders using it |
|---|---|---:|
| `ics` | LiveWhale, VPUL, CampusGroups `.ics` subscribe feeds | 4 |
| `tec_rest` | The Events Calendar (WordPress plugin) REST API | 6 |
| `jsonld` | Pages/APIs emitting schema.org `Event`/`SportsEvent` JSON-LD | 34 (3 standalone + 31 Athletics via generator) |
| `rss` | RSS feeds carrying a `<sdo:Event>` block | 1 |
| `html_css` | Declarative CSS-selector scraping of server-rendered HTML | 12 |
| `playwright_html` | Same as `html_css`, but via real headless Chromium for sites behind a genuine Cloudflare "managed" JS challenge | 10 |
| `almanac_calendar` | Bespoke parser for Almanac's category-accordion page shape | 1 |

## Wired feeders

Grouped as in `master.yaml`. `registry_url` is the exact `calendars.calendar_url`
match; see the YAML for full CSS selectors and per-source reasoning comments.

### ICS / CampusGroups

| id | host | registry_url |
|---|---|---|
| `vpul-university-life` | University Life | `ulife.vpul.upenn.edu/calendar/` |
| `psom-livewhale` | Perelman School of Medicine | `events.med.upenn.edu/` |
| `law-livewhale` | Penn Carey Law | `www.law.upenn.edu/calendar/` |
| `nursing-livewhale` | School of Nursing | `www.nursing.upenn.edu/calendar/` |
| `wharton-campusgroups` | The Wharton School | `groups.wharton.upenn.edu/events` |

Law's feed intermittently truncates at the CDN layer (a known upstream bug, not
ours) — `mark_absent_as_removed` self-heals it on the next run rather than
losing data.

### TEC REST API

| id | host | registry_url |
|---|---|---|
| `engineering-tec` | Penn Engineering | `events.engineering.upenn.edu/` |
| `vet-tec` | Penn Vet | `www.vet.upenn.edu/about/penn-vet-events-calendar` |
| `faculty-senate-tec` | Faculty Senate | `facultysenate.upenn.edu/events/` — **0 events currently** |
| `quiest-tec` | QUIEST | `quiest.seas.upenn.edu/` |
| `cetli-tec` | Center for Teaching and Learning | `cetli.upenn.edu/` |
| `penn-memory-center-tec` | Penn Memory Center | `pennmemorycenter.org/` — **0 events currently** |

### RSS

| id | host | registry_url |
|---|---|---|
| `sas-rss` | School of Arts & Sciences | `www.sas.upenn.edu/events/` |

### JSON-LD

| id | host | registry_url |
|---|---|---|
| `grasp-jsonld` | GRASP Lab | `www.grasp.upenn.edu/events/category/seminars/` |
| `epigenetics-jsonld` | Epigenetics Institute | `hosting.med.upenn.edu/epigenetics/calendar/list/` |
| `asset-jsonld` | ASSET Center | `asset.seas.upenn.edu/events/` |
| `athletics-teams` (generator, 31 feeds) | Athletics | `pennathletics.com/sports/<slug>/schedule` for every varsity team |

### `html_css` (plain HTTP, no bot-blocking)

| id | host | registry_url |
|---|---|---|
| `gse-html` | Penn GSE | `www.gse.upenn.edu/events` |
| `dental-html` | Penn Dental | `www.dental.upenn.edu/events/` |
| `design-html` | Stuart Weitzman School of Design | `www.design.upenn.edu/events` |
| `sp2-html` | SP2 | `www.sp2.upenn.edu/events/` |
| `penn-alumni-html` | Penn Alumni Relations | `www.alumni.upenn.edu/events` |

### `playwright_html` (headless Chromium — sites behind a genuine Cloudflare "managed" challenge)

| id | host | registry_url |
|---|---|---|
| `penn-today-html` | University | `penntoday.upenn.edu/events` |
| `annenberg-html` | Annenberg School for Communication | `www.asc.upenn.edu/news-events/events` |
| `library-html` | Penn Libraries | `www.library.upenn.edu/events` |
| `hss-html` | History and Sociology of Science | `hss.sas.upenn.edu/events` |
| `figs-html` | French, Italian & Germanic Studies | `figs.sas.upenn.edu/events` |
| `theatre-html` | Theatre Arts | `theatre.sas.upenn.edu/events` |
| `casi-html` | Center for the Advanced Study of India | `casi.sas.upenn.edu/events` |
| `psychology-html` | Psychology | `psychology.sas.upenn.edu/events` |
| `southasiacenter-html` | South Asia Center | `www.southasiacenter.upenn.edu/events` |
| `gsws-html` | Gender, Sexuality, and Women's Studies | `gsws.sas.upenn.edu/events` |
| `watercenter-html` | The Water Center at Penn | `watercenter.sas.upenn.edu/events/` |
| `ceet-html` | Center of Excellence in Environmental Toxicology | `ceet.upenn.edu/events/` |
| `isss-html` | International Student and Scholar Services | `global.upenn.edu/isss/events` |
| `penn-abroad-html` | Penn Abroad | `global.upenn.edu/pennabroad/events/` |
| `pci-html` | Penn Center for Innovation | `pci.upenn.edu/events/` |
| `snf-paideia-html` | SNF Paideia Program | `snfpaideia.upenn.edu/engage/events/` |

### Bespoke

| id | host | registry_url |
|---|---|---|
| `almanac-calendar` | University (Almanac) | `almanac.upenn.edu/at-penn-calendar` |

## Blocking mechanisms encountered (and how each was handled)

Three structurally different HTTP-403 causes were found and diagnosed
separately — never with UA spoofing or impersonation:

1. **Cloudflare "managed" JS challenge** (`cType: 'managed'`) — Penn Today,
   Annenberg, the SAS Drupal cluster, CEET, Penn Global, PCI, SNF Paideia, Penn
   Libraries, and ~45 more candidates found but not yet wired. Solved with a
   real headless Chromium browser (`playwright_html`) presenting our honest
   `PennEventsBot` identity and executing the actual challenge JS — not
   evasion, since nothing about our automated identity is hidden.
2. **nginx/WAF keyword false positive** — Almanac blocks any UA containing a
   `(+http...)`-style contact URL, contradicted by the site's own permissive
   `robots.txt`. Solved with a per-feeder UA override that drops only the
   flagged substring while staying a real, contactable identity — confirmed
   appropriate via robots.txt, not assumed.
3. **Infra-level block (`server: awselb/2.0`)** — 6 `*.upenn.edu` department
   sites (history, chem, ling, physics, polisci, africa, bio) return a bare 403
   for *every* client tested, including plain curl and Playwright, with no
   challenge page at all. This is an IP/ASN-level block, not bot detection —
   there is no legitimate client-side fix, so these are explicitly left
   unaddressed rather than worked around.

## Registry rows deliberately not wired (confirmed redundant, not just skipped)

Roughly 140 of the 511 registry rows look unwired but are already fully
captured by a feeder above — confirmed per-site, not assumed from the domain:

- **Global-API redundancy** (~50 rows): LiveWhale/TEC/CampusGroups expose one
  site-wide feed regardless of which page embeds the widget, so a department's
  "filtered view" page (e.g. 36 `events.med.upenn.edu/<group>/` rows, 11
  `www.law.upenn.edu/institutes/<x>/` rows, 10 `ulife.vpul.upenn.edu/<host>/`
  rows) is the exact same feed as the school-wide one already wired.
- **Duplicate single-page sites**: `italian.sas.upenn.edu` and
  `southasia.upenn.edu` are byte-for-byte identical to `figs.sas.upenn.edu` and
  `southasiacenter.upenn.edu` respectively (same titles, same dates) — not
  wired separately.
- **Homepages, not calendars**: 27 of 28 `library.upenn.edu` branch pages
  (`/dental`, `/vet`, `/museum`, …) render zero event cards — confirmed live,
  not merely assumed from the URL pattern.
- **Stale/wrong registry URLs (404)**: `spanish.sas.upenn.edu/events`,
  `annenbergpublicpolicycenter.org/events/`.
- **No server-rendered content, needs its own browser feeder**:
  `www.wharton.upenn.edu/events/` is a Salesforce Lightning ("EventsHQ")
  widget with nothing to scrape server-side. (Wharton's real event data comes
  from the separate `wharton-campusgroups` registry row instead.)

## Checked and found not (yet) wireable

Investigated live this pass, explicitly not pursued further because the
content genuinely isn't there or the yield doesn't justify a bespoke feeder:

- `ceas.sas.upenn.edu`, `cseri.sas.upenn.edu`, `prss.sas.upenn.edu` — real
  "Events" pages, but render **zero** events server-side right now.
- `wffi.wharton.upenn.edu`, `www.ldc.upenn.edu`, `www.publicsafety.upenn.edu`
  — registry URL is the site homepage; no event markup anywhere on the page.
- DBEI's `Center for Cancer Data Science` sub-page — no event markup found
  (only 1 of 7 DBEI center pages checked; the other 6 are unexplored).
- 4 of 5 Annenberg sub-center pages unexplored (only
  `center-for-media-at-risk` was checked: 0 matches against the main
  `annenberg-html` selector).

## Open / not yet investigated

- ~45 more Cloudflare-fronted candidates identified by the bulk probe but not
  yet individually selector-mapped.
- The broader Drupal (~93) / WordPress (~106) / plain-HTML (~69) pool from the
  original registry probe that wasn't Cloudflare-blocked — needs
  selector-by-selector work, one site at a time.
- 6 of 7 DBEI center pages, 4 of 5 Annenberg sub-centers, and a handful of
  misc singles (`global.upenn.edu/pwcc`, `alumni.wharton.upenn.edu/events-hq/`)
  not yet checked.
