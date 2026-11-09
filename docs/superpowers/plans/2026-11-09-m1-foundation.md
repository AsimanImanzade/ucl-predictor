# Milestone 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest real match history, rate every club with our own point-in-time Elo + Dixon-Coles baseline, and simulate the 2026/27 Champions League. The milestone ends with a CLI that prints pre-season (as of 2026-09-07) and live Top 8 / Top 24 / winner chances for all 36 teams.

**Architecture:** A Python package (`pipeline/`, uv) ingests data, builds a canonical match table, computes Elo, fits the baseline goal model and exports two JSON files per snapshot (`season.json` + `lambdas.json`). A TypeScript package (`sim/`, pnpm) consumes those files and runs the Monte Carlo tournament. The same package will later run in the browser.

**Tech Stack:**
- Python 3.13 (uv): pandas, pyarrow, numpy, scipy, scikit-learn, requests, python-dotenv, pytest, ruff
- Node 24 / TypeScript 5 (strict), pnpm 10, vitest, tsx

**Scope note:** engsoccerdata (CL 2005–2011) is deferred to Milestone 4, where pre-2011 pedigree features need it. Milestone 1's Elo burns in from 2010-11 domestic data and 2011-12 European data.

**Spec:** `docs/superpowers/specs/2026-11-09-ucl-predictor-design.md`. Also follow the project skills `applying-ucl-format-rules` (incl. `bracket-reference.md`), `ingesting-football-data` and `modeling-match-outcomes`.

## Global Constraints

- Season id format `"2026-27"`. All datetimes are UTC ISO-8601. Pre-season `as_of` = `2026-09-07T00:00:00Z`.
- **Point-in-time:** anything that takes `as_of` may only use matches with kickoff `< as_of`.
- **Goals:** models and Elo use **90-minute goals only**. Extra time and penalties never enter `home_goals`/`away_goals`.
- **Team id format:** `<country3 lowercase>-<slug of core name>`, e.g. `esp-atletico-madrid`, `eng-arsenal`. One club = one id across every source and season.
- **Secrets:** the API key is read only from env `FOOTBALL_DATA_TOKEN` (loaded from the git-ignored `.env`). Never print, log, commit or write it into raw caches.
- **football-data.org:** at most 10 requests/min (sleep ≥ 6.5 s between calls). Raw responses are cached under `data/raw/football-data/<YYYY-MM-DD>/`.
- **Tests:** unit tests never touch the network. Tests needing real data are marked `@pytest.mark.data`; tests needing the network are marked `@pytest.mark.network`. Both are skipped by default and run with `-m data` / `-m network`.
- **Seeds:** every simulation takes an explicit seed. Official runs use 50,000 runs, seed 1.
- **Attribution text (verbatim, in README):** `Football data provided by the Football-Data.org API`
- **2026/27 final venue team:** `esp-atletico-madrid` (it hosts the final if it qualifies; otherwise the final is neutral).
- **Model name string:** `elo-dc-v1`.

## Review Focus

1. **One club, two names** ("SL Benfica" vs "Sport Lisboa e Benfica") silently splits a club's history and weakens its rating. Expected: both map to one id. Tests in Tasks 2 and 6.
2. **Postponed, suspended or cancelled CL fixtures** must count as unplayed and still be simulated, and the fixture count stays 144. Tests in Tasks 4 and 9.
3. **The `as_of` boundary:** a match kicking off at 2026-09-08 16:45 UTC must be unplayed in the pre-season export and absent from the model fit. Tests in Tasks 8 and 9.
4. **Extra-time and penalty scores** ("4-2 pen. 1-1 a.e.t.") must never leak into 90-minute goals. Tests in Tasks 3 and 4.
5. **A club with no or very little history** must get a seeded Elo and finite λ, never NaN or 0. Tests in Tasks 7 and 9.

---

### Task 1: Monorepo scaffold and toolchain

**Files:**
- Create: `pipeline/pyproject.toml`, `pipeline/src/uclpred/__init__.py`, `pipeline/src/uclpred/config.py`, `pipeline/tests/test_smoke.py`
- Create: `package.json`, `pnpm-workspace.yaml`, `sim/package.json`, `sim/tsconfig.json`, `sim/src/index.ts`, `sim/tests/smoke.test.ts`
- Create: `README.md`; Modify: `.gitignore`

**Interfaces:**
- Produces, in `uclpred.config`:
  - `ROOT: Path`, `DATA: Path` (= ROOT/"data"), `RAW`, `PROCESSED`, `REFERENCE`, `EXPORT` (= DATA/"export"), `REPORTS` (= ROOT/"reports")
  - `SEASON = "2026-27"`, `PRESEASON_AS_OF = datetime(2026, 9, 7, tzinfo=UTC)`, `FINAL_VENUE_TEAM = "esp-atletico-madrid"`, `MODEL_NAME = "elo-dc-v1"`
- Produces: `sim` package name `@uclpred/sim`, ESM, with scripts `test` (vitest run) and `cli` (tsx src/cli.ts).

- [ ] **Step 1: Install the toolchain.** Read `https://astral.sh/uv/install.sh` before running it, then install uv. Enable pnpm with `corepack enable pnpm`; if that fails on permissions, run `npm install -g pnpm@10`.
  Verify: `uv --version` and `pnpm --version` both print versions.
- [ ] **Step 2: Create the Python project.** `uv init --package --name uclpred pipeline`, then `uv python pin 3.13`. Add the runtime deps (pandas, pyarrow, numpy, scipy, scikit-learn, requests, python-dotenv) and dev deps (pytest, ruff). Add a console script `uclpred = "uclpred.cli:main"`. In pytest config, register the markers `data` and `network` and set `addopts = "-m 'not data and not network'"`.
- [ ] **Step 3: Write `config.py`** with the constants above, and a smoke test asserting `PRESEASON_AS_OF.isoformat() == "2026-09-07T00:00:00+00:00"`.
  Run: `cd pipeline && uv run pytest -v`. Expected: 1 passed.
- [ ] **Step 4: Create the pnpm workspace.**
  - `pnpm-workspace.yaml` lists `sim`.
  - `sim` has typescript, vitest and tsx as dev deps.
  - `tsconfig.json`: `strict: true`, `noUncheckedIndexedAccess: true`, `module/moduleResolution: "NodeNext"`.
  - Smoke test: `expect(1 + 1).toBe(2)`.
  Run: `pnpm --filter @uclpred/sim test`. Expected: 1 passed.
- [ ] **Step 5: Update `.gitignore`** with `data/processed/`, `data/export/` and `.pytest_cache/`. Write `README.md`: one paragraph on what the project is, how to set it up (`uv sync`, `pnpm install`, a `.env` with `FOOTBALL_DATA_TOKEN`) and the attribution line.
- [ ] **Step 6: Commit** — `chore: scaffold pipeline (uv) and sim (pnpm) packages`

---

### Task 2: Team identity resolver

**Files:**
- Create: `pipeline/src/uclpred/teams.py`, `data/reference/team_aliases.csv`, `pipeline/tests/test_teams.py`

**Interfaces:**
- Produces:
  - `ISO3_TO_FIFA: dict[str, str]` = `{"DEU":"GER","GRC":"GRE","NLD":"NED","CHE":"SUI","DNK":"DEN","HRV":"CRO","BGR":"BUL","PRT":"POR"}`. Any other code passes through unchanged.
  - `LEAGUE_COUNTRY: dict[str, str]` = `{"en":"ENG","sco":"SCO","de":"GER","es":"ESP","fr":"FRA","it":"ITA","nl":"NED","pt":"POR","at":"AUT","be":"BEL","gr":"GRE","tr":"TUR"}`
  - `core_name(name: str) -> str`
  - `class TeamResolver(aliases_path: Path)` with `.resolve(country: str, name: str) -> str` (returns a team id) and `.core(country, name) -> str` (the core name after aliases are applied).
- `team_aliases.csv` columns: `country,variant_core,canonical_core`.

- [ ] **Step 1: Write the failing tests.**
  - `core_name("Club Atlético de Madrid") == core_name("Atlético Madrid") == "atletico madrid"`
  - `core_name("Real Madrid CF") == "real madrid"`
  - `core_name("ŠK Slovan Bratislava") == core_name("Slovan Bratislava") == "slovan bratislava"`
  - `core_name("Stade Brestois 29") == "stade brestois"`
  - `core_name("PAE AEK") == "aek"`
  - `core_name("Lille OSC") == "lille"`
  - With an alias row `POR,sport lisboa e benfica,benfica`: `resolve("POR","Sport Lisboa e Benfica") == resolve("POR","SL Benfica") == "por-benfica"`
  - `resolve("DEU","FC Bayern München") == "ger-bayern-munchen"`
  - Raises `ValueError` on an empty name.
- [ ] **Step 2: Run** `uv run pytest tests/test_teams.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement `core_name`.**
  - NFKD-strip accents, lowercase, replace punctuation with spaces.
  - Drop tokens that are pure digits.
  - Drop stop-tokens: `{fc, cf, sc, ac, afc, ssc, sk, fk, kv, club, de, da, the, cd, sl, pae, bsc, as, rc, osc, sv, ud, sd, nk, hnk, gnk, pfc, kf, if, ff, bk}`.
  - Collapse whitespace.
  Implement `TeamResolver.resolve` as `f"{FIFA(country).lower()}-{slug(alias(core))}"`, where slug replaces spaces with `-`. Seed `team_aliases.csv` with the Benfica row only; Task 6 grows it from the audit.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pipeline): team identity resolver with alias table`

---

### Task 3: openfootball Football.TXT parser (European competitions)

**Files:**
- Create: `pipeline/src/uclpred/ingest/__init__.py`, `pipeline/src/uclpred/ingest/http_cache.py`, `pipeline/src/uclpred/ingest/openfootball_txt.py`
- Create: `pipeline/tests/fixtures/of_sample.txt`, `pipeline/tests/test_openfootball_txt.py`

**Interfaces:**
- Produces:
  - `http_cache.get_cached(url: str, cache_path: Path, headers: dict | None = None, min_interval_s: float = 0.0) -> bytes`: returns the file if it exists, otherwise downloads and writes it.
  - `RawMatch` dataclass: `date: datetime` (UTC; 12:00 if no time given), `stage: str`, `home_name: str`, `home_country: str`, `away_name: str`, `away_country: str`, `home_goals: int | None`, `away_goals: int | None`, `et_home: int | None`, `et_away: int | None`, `pens_home: int | None`, `pens_away: int | None`, `neutral: bool`
  - `parse_football_txt(text: str, season: str) -> list[RawMatch]`
  - `EURO_FILES = {"cl":"uefa.cl","clq":"uefa.clq","el":"uefa.el","elq":"uefa.elq","conf":"uefa.ecl","confq":"uefa.eclq"}`
  - `load_openfootball_euro(season: str) -> list[tuple[str, RawMatch]]` returns (competition code, match) pairs. It fetches `https://raw.githubusercontent.com/openfootball/champions-league/master/{season}/{file}.txt` for each file that exists, caching under `data/raw/openfootball/`. Seasons run from `2011-12` to `2025-26`.

- [ ] **Step 1: Create the fixture `of_sample.txt`** with these real lines, verbatim: the `▪ League, Matchday 1` block from 2024-25 `cl.txt` (first 2 dates), a `▪ Group A` header, and these knockout lines:
  `20:45  Real Madrid (ESP)       v Atlético Madrid (ESP)    4-1 a.e.t. (1-1, 0-1)`
  `21:00  AS Roma (ITA)           v Feyenoord (NED)          4-2 pen. 1-1 a.e.t. (1-1, 1-1)`
  `17:45  FK Kairat (KAZ)         v Celtic FC (SCO)          3-2 pen. 0-0 a.e.t. (0-0)`
  `19:00  The New Saints (WAL)    v KF Shkëndija 79 (MKD)    0-0`
  …placed under a `▪ Final` header for one of them, and a date line without a year (`  Wed Sep 18`).
- [ ] **Step 2: Write the failing tests.**
  - The match count equals the number of match lines.
  - Young Boys v Aston Villa → `home_goals=0, away_goals=3`, `home_country="SUI"`, `date=2024-09-17 18:45 UTC`.
  - A line with no time inherits the previous time.
  - A date without a year inherits the year from the previous date; if the month goes backwards, add 1 year.
  - `"4-1 a.e.t. (1-1, 0-1)"` → 90-min `1-1`, `et_home=4, et_away=1`, `pens None`.
  - `"4-2 pen. 1-1 a.e.t. (1-1, 1-1)"` → 90-min `1-1`, `pens 4-2`.
  - `"3-2 pen. 0-0 a.e.t. (0-0)"` → 90-min `0-0`.
  - `"0-0"` with no parentheses → 90-min `0-0`.
  - A match under `▪ Final` or `▪ Finals, Final` → `neutral=True`; everything else is `False`.
  - Team names keep their internal spaces, e.g. `"KF Shkëndija 79"`.
- [ ] **Step 3: Run** `uv run pytest tests/test_openfootball_txt.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement the parser.** A line-oriented state machine: the current stage (from `▪`), the current date (from weekday-prefixed lines) and the current time. Match regex: optional `HH:MM`, then `(?P<h>.+?) \((?P<hc>[A-Z]{3})\)\s+v\s+(?P<a>.+?) \((?P<ac>[A-Z]{3})\)\s+(?P<score>.+)`.
  Score rules:
  - If `a.e.t.` is present, the 90-min score is the first `X-Y` inside the parentheses, and the score right before `a.e.t.` is ET.
  - If `pen.` is present, the score before it is penalties.
  - Otherwise the leading `X-Y` is 90 min.
  - Lines without a score (fixtures not yet played) give `None` goals.
  Then implement `get_cached` (requests, timeout 30 s) and `load_openfootball_euro`; a 404 for a missing file is skipped.
- [ ] **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(pipeline): parse openfootball European competition files`

---

### Task 4: Domestic football.json loader and football-data.org client

**Files:**
- Create: `pipeline/src/uclpred/ingest/openfootball_json.py`, `pipeline/src/uclpred/ingest/football_data.py`
- Create: `pipeline/tests/fixtures/fd_matches_sample.json`, `pipeline/tests/fixtures/ofjson_sample.json`, `pipeline/tests/test_domestic_and_fd.py`

**Interfaces:**
- Consumes: `RawMatch` and `get_cached` (Task 3).
- Produces:
  - `load_football_json(season: str, code: str) -> list[RawMatch]` from `https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{code}.json`. The country comes from `LEAGUE_COUNTRY[code.split('.')[0]]`, `neutral=False`, and the time defaults to 12:00 UTC.
  - `DOMESTIC_CODES = ["en.1","en.2","de.1","de.2","es.1","es.2","fr.1","fr.2","it.1","it.2","nl.1","pt.1","at.1","be.1","gr.1","tr.1","sco.1"]`. Missing (season, code) files are skipped.
  - `FD_COMPETITIONS = {"CL":"uefa.cl","PL":"en.1","PD":"es.1","BL1":"de.1","SA":"it.1","FL1":"fr.1","DED":"nl.1","PPL":"pt.1"}`
  - `FdMatch` dataclass: every `RawMatch` field plus `fd_id: int`, `matchday: int | None`, `status: str`, `home_fd_id: int`, `away_fd_id: int`, `home_tla: str`, `away_tla: str`, `home_crest: str`, `away_crest: str`
  - `class FootballDataClient(token: str)` with:
    - `.matches(code: str, season: int) -> list[dict]` (raw JSON matches)
    - `.teams(code: str, season: int) -> list[dict]`
    - Requests are spaced ≥ 6.5 s apart, cached by date, and raise `PermissionError` on HTTP 403.
  - `normalize_fd_match(m: dict, team_country: dict[int, str]) -> FdMatch`
  - `PLAYED_STATUSES = {"FINISHED", "AWARDED"}`

- [ ] **Step 1: Build the fixtures.**
  - `fd_matches_sample.json`: copy 4 real matches from `GET /v4/competitions/CL/matches?season=2025` — one REGULAR, one EXTRA_TIME, one PENALTY_SHOOTOUT and one FINAL. Edit a copy of the REGULAR match to `"status":"POSTPONED"` with null scores.
  - `ofjson_sample.json`: copy 3 matches from 2025-26 `tr.1.json`, one of them with no `score` key.
- [ ] **Step 2: Write the failing tests.**
  - EXTRA_TIME match → `home_goals/away_goals == score.regularTime` and `et_* == score.fullTime`.
  - PENALTY_SHOOTOUT → `pens_* == score.penalties`, and the 90-min goals come from `regularTime`.
  - REGULAR → 90-min = `fullTime`.
  - stage `FINAL` → `neutral=True`.
  - POSTPONED → `status=="POSTPONED"`, goals `None`.
  - `home_country` uses `ISO3_TO_FIFA`, so `DEU→GER`.
  - The football.json match without `score` → goals `None`; `Galatasaray` gets country `TUR`.
  - `FootballDataClient` never puts the token into a cache file name or the cached body (test with a fake token and a monkeypatched `requests.get`).
- [ ] **Step 3: Run** `uv run pytest tests/test_domestic_and_fd.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement both modules.** `team_country` comes from `.teams()` (`area.code` per team id). The client reads `X-Requests-Available`; if it is 0, sleep until `X-RequestCounter-Reset`.
- [ ] **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(pipeline): football.json and football-data.org ingestion`

---

### Task 5: Canonical match table and `uclpred ingest`

**Files:**
- Create: `pipeline/src/uclpred/matches.py`, `pipeline/src/uclpred/cli.py`, `pipeline/tests/test_matches.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces:
  - `MATCH_COLUMNS = ["match_id","date","season","competition","stage","home_id","away_id","home_goals","away_goals","neutral","status","source"]`. `date` is tz-aware UTC; goals are `Int64`; `status` is `"FINISHED"` or `"SCHEDULED"`; `source` is `"football-data"` or `"openfootball"`.
  - `to_frame(rows: list[tuple[str, str, RawMatch | FdMatch, str]], resolver: TeamResolver) -> pd.DataFrame` (rows are competition, season, match, source)
  - `season_label(start_year: int) -> str`: e.g. `2025 → "2025-26"`, used for football-data seasons
  - `combine(frames: list[pd.DataFrame]) -> pd.DataFrame`: for each `(competition, season)` it keeps only the highest-priority source (`football-data` > `openfootball`), then sorts by date.
  - `validate_matches(df: pd.DataFrame) -> None`: raises `ValueError` listing every problem.
  - `load_matches() -> pd.DataFrame`: reads `data/processed/matches.parquet`.
  - CLI `uclpred ingest`:
    - openfootball euro for 2011-12..2025-26
    - football.json `DOMESTIC_CODES` for 2010-11..2026-27
    - football-data `CL` for 2024, 2025, 2026 and the 7 leagues for 2025, 2026 (a 403 is logged and skipped)
    - → `data/processed/matches.parquet`, plus `data/processed/cl_2026_fd.json` (the raw 2026 CL matches) and `data/processed/cl_2026_teams.json`

- [ ] **Step 1: Write the failing tests** using in-memory RawMatch/FdMatch objects.
  - `match_id` is `fd:<id>` for football-data, or `of:<competition>:<date>:<home_id>:<away_id>`.
  - Priority: the same (uefa.cl, 2025-26) from both sources → only football-data rows remain; (uefa.clq, 2025-26) from openfootball is kept.
  - `validate_matches` flags a duplicate (date, home_id, away_id), negative goals, FINISHED without goals, and `home_id == away_id`.
  - Status: goals present → `FINISHED`; `None` → `SCHEDULED`; football-data uses `PLAYED_STATUSES`.
- [ ] **Step 2: Run** `uv run pytest tests/test_matches.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** `matches.py` and the `ingest` subcommand (argparse; `main()` dispatches subcommands; loads `.env` from the repo root with python-dotenv).
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Run the real ingest** with `uv run uclpred ingest`. Expected: it finishes and prints a per-competition row count; `uefa.cl 2026-27` has 144 rows, 72 of them FINISHED as of 2026-11-09.
- [ ] **Step 6: Commit** — `feat(pipeline): canonical match table and ingest command`

---

### Task 6: Coefficients, coverage audit and alias curation

**Files:**
- Create: `pipeline/src/uclpred/ingest/uefa_coefficients.py`, `pipeline/src/uclpred/coverage.py`, `pipeline/tests/test_coverage.py`
- Create: `data/reference/coefficients.csv`, `reports/coverage.md`; Modify: `data/reference/team_aliases.csv`

**Interfaces:**
- Produces:
  - `fetch_coefficients(season_year: int) -> pd.DataFrame` from `https://comp.uefa.com/v2/coefficients?coefficientRange=OVERALL&coefficientType=MEN_CLUB&language=EN&page=1&pagesize=500&seasonYear={season_year}`, with columns `season_year, team_id, name, country, total_5y` (inspect the JSON once to map fields). It is appended or replaced in `coefficients.csv`.
  - `duplicate_candidates(df: pd.DataFrame) -> list[tuple[str, str]]`: id pairs with the same country prefix where one core's token set is a subset of the other's, or `difflib.SequenceMatcher` ratio ≥ 0.85, **and** the two ids never appear in the same match.
  - `coverage_report(df, cl_teams: list[dict], coefs: pd.DataFrame) -> str` (Markdown). For each of the 36 teams it gives: team id, matches total, matches in the last 3 seasons, first match date, current-season domestic source (`football-data` / `openfootball` / `missing`) and coefficient present (yes/no).
  - CLI: `uclpred coefficients --season-year 2026`, `uclpred coverage`

- [ ] **Step 1: Write the failing tests.** `duplicate_candidates` returns `("por-benfica","por-sport-lisboa-e-benfica")` for a frame with those two ids in different matches. It does not return two ids that played each other. `coverage_report` marks a team with no matches as `0` without crashing.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Curation loop on real data.**
  1. Run `uclpred coefficients --season-year 2026`, then `uclpred coverage`.
  2. For each duplicate candidate, decide whether it is the same club. If so, add an alias row (`country,variant_core,canonical_core`). Use the football-data.org spelling's core as canonical.
  3. Re-run `ingest` and `coverage` until all of these hold:
     - every one of the 36 teams has a coefficient,
     - no remaining candidate involves one of the 36 teams,
     - every team except genuine newcomers has ≥ 20 matches.
  The report's "missing domestic" list should match the 11 teams named in the spec.
- [ ] **Step 6: Commit** — `feat(pipeline): coefficients, coverage audit and curated team aliases` (include `reports/coverage.md` and both CSVs).

---

### Task 7: Point-in-time Elo engine

**Files:**
- Create: `pipeline/src/uclpred/elo.py`, `pipeline/tests/test_elo.py`

**Interfaces:**
- Consumes: the canonical match DataFrame (Task 5).
- Produces:
  - `@dataclass EloParams`: `k=20.0, home_adv=60.0, init_top=1500.0, init_second=1350.0, init_unknown=1400.0`
  - `expected_home(r_home: float, r_away: float, home_adv: float) -> float` = `1/(1+10**((r_away-r_home-home_adv)/400))`
  - `mov_multiplier(goal_diff: int) -> float`: 1.0 if |gd| ≤ 1, 1.5 if |gd| = 2, otherwise `(11+|gd|)/8`
  - `run_elo(matches: pd.DataFrame, params: EloParams = EloParams()) -> EloResult`
  - `EloResult.pre: pd.DataFrame` (`match_id, home_elo_pre, away_elo_pre`)
  - `EloResult.rating_as_of(team_id: str, as_of: datetime) -> float | None`
  - `EloResult.ratings_as_of(as_of: datetime) -> dict[str, float]`

- [ ] **Step 1: Write the failing tests.**
  - `expected_home(1500,1500,0) == 0.5`
  - `expected_home(1500,1500,60) > 0.5`
  - `mov_multiplier(1)==1.0`, `mov_multiplier(2)==1.5`, `mov_multiplier(4)==15/8`
  - Two equal teams draw away from home → the ratings change by `k*(0.5-expected)` symmetrically and the sum is conserved.
  - **Point-in-time:** `pre` for a match equals `rating_as_of(team, match.date)` and never includes that match's result. `rating_as_of(team, date_before_first_match)` is `None`.
  - **Seeding:**
    - first appearance in `xx.1` with ≥ 5 already-rated teams in that competition → the mean of their current ratings;
    - otherwise `init_top`;
    - `.2` → `init_second`;
    - first appearance in a `uefa.*` competition → the mean of rated teams from the same country prefix if ≥ 3 exist, else `init_unknown`.
  - Neutral matches use `home_adv=0`. SCHEDULED rows are ignored.
- [ ] **Step 2: Run** `uv run pytest tests/test_elo.py -v`. Expected: FAIL. **Step 3: Implement** a single chronological pass that stores, per team, a sorted list of `(datetime, rating_after)`; `rating_as_of` uses `bisect` on strictly earlier dates. **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real-data check** (`@pytest.mark.data`, `test_elo_real.py`): as of `PRESEASON_AS_OF`, the top 10 by Elo among the 36 teams includes at least 6 of {Real Madrid, Bayern, PSG, Inter, Arsenal, Liverpool, Man City, Barcelona}.
  Run: `uv run pytest -m data tests/test_elo_real.py -v`. Expected: PASS.
- [ ] **Step 6: Commit** — `feat(pipeline): point-in-time Elo ratings`

---

### Task 8: Score matrix and baseline goal model (Elo + Dixon-Coles)

**Files:**
- Create: `pipeline/src/uclpred/models/__init__.py`, `models/score_matrix.py`, `models/baseline.py`, `models/metrics.py`
- Create: `pipeline/tests/test_score_matrix.py`, `pipeline/tests/test_baseline.py`, `pipeline/tests/test_baseline_real.py`

**Interfaces:**
- Consumes: matches (Task 5), `EloResult` (Task 7).
- Produces:
  - `score_matrix(lh: float, la: float, rho: float, max_goals: int = 10) -> np.ndarray`: shape (11, 11), sums to 1. The Dixon-Coles τ is applied as (0,0): `1-lh*la*rho`, (0,1): `1+lh*rho`, (1,0): `1+la*rho`, (1,1): `1-rho`; then renormalise.
  - `outcome_probs(m: np.ndarray) -> tuple[float, float, float]` = (home, draw, away)
  - `metrics.rps(probs: np.ndarray, outcomes: np.ndarray) -> float` (mean ranked probability score; outcomes 0 = home, 1 = draw, 2 = away)
  - `fit_baseline(matches, elo: EloResult, as_of: datetime, xi: float = 0.0019, window_days: int = 1460, alpha: float = 0.005, euro_weight: float = 2.0) -> BaselineModel`
  - `BaselineModel`:
    - `.as_of`, `.rho: float`
    - `.lambdas(team_a: str, team_b: str, venue: Literal["home","neutral"]) -> tuple[float, float]` (team_a hosts when venue == "home"; uses Elo as of `.as_of`)
    - `.predict_match(home_id, away_id, neutral=False) -> np.ndarray`
- **Model:** a weighted Poisson GLM (`sklearn.linear_model.PoissonRegressor(alpha=alpha)`, sparse design) over two rows per match:
  `log λ = μ + h·is_home + β·(elo_team − elo_opp)/100 + attack[team] + defence[opp]`
  - Weights: `exp(−xi·days_before_as_of) × (euro_weight if competition starts "uefa." else 1)`.
  - Training rows: FINISHED matches with `as_of − window_days ≤ date < as_of`.
  - A team unseen in the window → attack = defence = 0.
  - `rho` = argmax over [−0.25, 0.25] of the weighted Σ log τ(hg, ag; λh, λa, ρ) (`scipy.optimize.minimize_scalar`, bounded).

- [ ] **Step 1: Write the failing tests.**
  - `score_matrix(1.5,1.1,0).sum()≈1`; with rho = 0 its (2,1) cell equals `poisson(1.5).pmf(2)*poisson(1.1).pmf(1)` up to renormalisation.
  - `rho=-0.1` raises the (0,0) and (1,1) cells relative to rho = 0.
  - **Golden values** (shared with Task 10): `outcome_probs(score_matrix(1.5,1.1,-0.1))` rounded to 6 dp. Compute and paste the three numbers into both the Python and TS tests.
  - `rps` of a perfect forecast is 0, and `rps([[1/3]*3],[0]) ≈ 0.2777778`.
  - On a synthetic league where team A always beats B 3-0: `λ_A > λ_B`; raising A's Elo raises λ_A.
  - **Leak test:** adding a match dated exactly `as_of` with an absurd score (20-0) leaves the fitted parameters unchanged.
- [ ] **Step 2: Run** the tests. Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real-data sanity** (`test_baseline_real.py`, `@pytest.mark.data`):
  - Fit at `2025-09-01`, predict all 144 `uefa.cl` 2025-26 league-phase matches.
  - Assert RPS < the base-rate RPS, where base rates are the home/draw/away shares of `uefa.cl` 2011-12..2024-25 matches. Print both numbers.
  Run: `uv run pytest -m data tests/test_baseline_real.py -v -s`. Expected: PASS, with the numbers printed.
- [ ] **Step 6: Commit** — `feat(pipeline): Elo + Dixon-Coles baseline goal model`

---

### Task 9: Snapshot export (`season.json` + `lambdas.json`)

**Files:**
- Create: `pipeline/src/uclpred/export.py`, `pipeline/tests/test_export.py`

**Interfaces:**
- Consumes: `cl_2026_fd.json` and `cl_2026_teams.json` (Task 5), `TeamResolver`, `coefficients.csv` (season_year 2026), `run_elo`, `fit_baseline`.
- Produces:
  - `build_season(fd_matches: list[dict], fd_teams: list[dict], resolver, coefs: dict[str, float], as_of: datetime) -> dict`, shaped:
    `{"season":"2026-27","asOf":ISO,"finalVenueTeamId":"esp-atletico-madrid","teams":[{"id","fdId","name","shortName","tla","crest","country","coefficient"}],"fixtures":[{"id","matchday","utcDate","homeId","awayId","played","homeGoals","awayGoals"}]}`
    A fixture is `played` only if its status is in `PLAYED_STATUSES` **and** its kickoff is `< as_of`; otherwise `played: false` and goals are `null`.
  - `build_lambdas(model: BaselineModel, team_ids: list[str]) -> dict`, shaped:
    `{"asOf","model":"elo-dc-v1","rho","teams":[...],"home":[[ [λi,λj] | null ]],"neutral":[[...]]}`
    `home[i][j]` means team i hosts team j; the diagonal is `null`.
  - `validate_snapshot(season: dict, lambdas: dict) -> None`: 36 teams; 144 fixtures; each team has 8 fixtures, 4 home and 4 away; every λ is finite and in [0.05, 6.0]; the team order is identical in both files.
  - CLI: `uclpred export --as-of 2026-09-07 --out data/export/md00` and `uclpred export --as-of now --out data/export/live`

- [ ] **Step 1: Write the failing tests** with synthetic fd dicts.
  - A fixture at `2026-09-08T16:45:00Z` with status FINISHED is unplayed when `as_of=2026-09-07`.
  - POSTPONED → unplayed and still counted among the 144.
  - `validate_snapshot` raises on 143 fixtures, on a team with 5 home games, and on a NaN λ.
  - `build_lambdas` matrices are 36×36 with a `null` diagonal.
  - A team with no history (a model where it is unseen) still gets λ in [0.05, 6].
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3: Implement** (`as_of="now"` → current UTC time). **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Real export.** Run both CLI commands. Expected: `data/export/md00/` and `data/export/live/` each contain both files, and validation passes. md00 has 0 played fixtures; live has 72 as of 2026-11-09.
- [ ] **Step 6: Commit** — `feat(pipeline): export season and lambda snapshots`

---

### Task 10: Simulator core — types, RNG, score sampling

**Files:**
- Create: `sim/src/types.ts`, `sim/src/rng.ts`, `sim/src/scores.ts`, `sim/tests/scores.test.ts`

**Interfaces:**
- Produces (`types.ts`, mirroring the Task 9 JSON exactly):
  - `TeamId = string`
  - `Team {id; fdId; name; shortName; tla; crest; country; coefficient: number}`
  - `Fixture {id: number; matchday: number; utcDate: string; homeId; awayId; played: boolean; homeGoals: number|null; awayGoals: number|null}`
  - `Season {season; asOf; finalVenueTeamId: TeamId|null; teams: Team[]; fixtures: Fixture[]}`
  - `Lambdas {asOf; model; rho: number; teams: TeamId[]; home: ([number,number]|null)[][]; neutral: ([number,number]|null)[][]}`
  - `Overrides = Record<number, {homeGoals: number; awayGoals: number}>`
  - `Stage = 'po'|'r16'|'qf'|'sf'|'final'|'winner'`
  - `TeamChances {teamId; position: number[] /*length 36*/; top8; top24; out; reach: Record<Stage, number>; expectedPoints: number}`
  - `SimResult {runs; seed; asOf; chances: TeamChances[]}`
- `createRng(seed: number): () => number` (mulberry32, values in [0,1))
- `scoreMatrix(lh: number, la: number, rho: number, maxGoals = 10): Float64Array` (the same τ as Task 8)
- `outcomeProbs(m: Float64Array, maxGoals = 10): [number, number, number]`
- `class ScoreSampler(lambdas: Lambdas)` with:
  - `sample(a: TeamId, b: TeamId, venue: 'home'|'neutral', rng): [number, number]` (cached CDF per pair and venue)
  - `lambda(a, b, venue): [number, number]`
- `samplePoisson(lambda: number, rng): number`

- [ ] **Step 1: Write the failing tests.**
  - The same seed gives the same first 5 numbers; different seeds differ.
  - `outcomeProbs(scoreMatrix(1.5,1.1,-0.1))` equals the Task 8 golden values within 1e-6.
  - 100k samples for one pair → the empirical home/draw/away shares are within 0.01 of `outcomeProbs`.
  - The mean of `samplePoisson(0.5)` over 100k draws is within 0.02 of 0.5.
- [ ] **Step 2: Run** `pnpm --filter @uclpred/sim test -- tests/scores.test.ts`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(sim): types, seeded RNG and Dixon-Coles score sampling`

---

### Task 11: League table and tiebreakers

**Files:**
- Create: `sim/src/table.ts`, `sim/src/tiebreak.ts`, `sim/tests/tiebreak.test.ts`

**Interfaces:**
- Produces:
  - `TeamRecord {id; played; won; drawn; lost; gf; ga; gd; pts; awayGf; awayWins; opponents: TeamId[]}`
  - `buildRecords(teamIds: TeamId[], results: Array<{homeId; awayId; homeGoals: number; awayGoals: number}>): Map<TeamId, TeamRecord>`
  - `rankTable(records: Map<TeamId, TeamRecord>, coefficient: Map<TeamId, number>): TeamId[]`
  - **Sort key** (all descending except the last): pts, gd, gf, awayGf, won, awayWins, Σ opponents' pts, Σ opponents' gd, Σ opponents' gf, coefficient; then team id ascending. Discipline (criterion 9) is skipped, with a code comment saying why.

- [ ] **Step 1: Write the failing tests** (hand-built results).
  - Points ordering.
  - A three-way tie on pts, gd and gf, resolved by away goals, applied across all three at once (no head-to-head).
  - A tie resolved by opponents' collective points.
  - A full tie resolved by coefficient.
  - `buildRecords` stats for one known team (W/D/L/GF/GA/pts/awayGf/awayWins).
- [ ] **Step 2: Run** `pnpm --filter @uclpred/sim test -- tests/tiebreak.test.ts`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(sim): league-phase table and UEFA tiebreakers`

---

### Task 12: Knockout bracket and tie resolution

**Files:**
- Create: `sim/src/bracket.ts`, `sim/src/tie.ts`, `sim/tests/knockout.test.ts`

**Interfaces:**
- Consumes: `ScoreSampler` and `samplePoisson` (Task 10).
- Produces:
  - `PlayoffTie {seeded: TeamId; unseeded: TeamId}`
  - `drawPlayoffs(ranking: TeamId[], rng): PlayoffTie[]`: 8 ties in **line order** A (9/10 v 23/24), B (11/12 v 21/22), C (13/14 v 19/20), D (15/16 v 17/18), two ties per line; inside each line a coin flip picks the pairing.
  - `R16Slot {top: TeamId; playoffTie: number}`
  - `drawBracket(ranking: TeamId[], rng): R16Slot[]`: 8 slots in bracket order. Each half is `[seed from {1,2}, seed from {7,8}, seed from {3,4}, seed from {5,6}]`; slots 0–3 are half 1 and 4–7 half 2. Each pair is split across the halves by a coin flip.
    - Pair {1,2} gets the two line-D ties, {3,4} line C, {5,6} line B, {7,8} line A; a coin flip decides which top seed takes which tie of its line.
    - QF pairings: slots (0,1), (2,3), (4,5), (6,7). SF: QF0 v QF1 and QF2 v QF3.
  - `playTwoLegged(firstHome: TeamId, secondHome: TeamId, sampler, rng): TeamId`
    - Aggregate of both legs (no away goals). If level → extra time in leg 2: Poisson with each side's leg-2 λ × 30/90. Still level → penalties 50/50.
  - `playFinal(a: TeamId, b: TeamId, venueTeamId: TeamId|null, sampler, rng): TeamId`
    - If `venueTeamId` is a or b, that team plays at home (`'home'` venue); otherwise `'neutral'`. Level → ET → penalties.
  - Leg order: play-off and R16 → the seeded/top team hosts leg 2; QF/SF → a coin flip.

- [ ] **Step 1: Write the failing tests.**
  - Over 10k `drawPlayoffs` with a fixed ranking: position 9's opponent ∈ {23, 24}, position 15's ∈ {17, 18}.
  - Over 10k `drawBracket`: positions 1 and 2 are always in different halves, as are 3/4, 5/6 and 7/8. Slot pairs (0,1) always hold one of {1,2} with one of {7,8}.
  - A two-legged tie with forced scores, built with a stub sampler returning fixed scores (1-0 then 0-1), always goes to ET/pens and never uses away goals.
  - `playFinal` with `venueTeamId` equal to team a calls the sampler with `venue 'home'` and a as host.
- [ ] **Step 2: Run** `pnpm --filter @uclpred/sim test -- tests/knockout.test.ts`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** — `feat(sim): knockout bracket draw and two-legged ties`

---

### Task 13: Tournament simulation and CLI first run

**Files:**
- Create: `sim/src/simulate.ts`, `sim/src/cli.ts`, `sim/tests/simulate.test.ts`; Modify: `sim/src/index.ts` (re-export the public API)
- Create: `reports/m1-first-run.md`

**Interfaces:**
- Consumes: Tasks 10–12.
- Produces:
  - `simulate(season: Season, lambdas: Lambdas, opts: {runs: number; seed: number; overrides?: Overrides}): SimResult`
    - Per run: played fixtures and overrides are fixed; others are sampled (venue `'home'`). Then rank → play-offs → bracket → R16 → QF → SF → final.
    - `position[k]` = P(finishing k+1); `top8` = P(pos ≤ 8); `top24` = P(pos ≤ 24); `out` = P(pos ≥ 25)
    - `reach.po` = P(9 ≤ pos ≤ 24); `reach.r16` = P(in R16); likewise `qf`, `sf`, `final`, `winner`
    - `expectedPoints` = mean final league points
  - CLI `pnpm --filter @uclpred/sim cli -- --input data/export/<label> [--runs 50000] [--seed 1]`: writes `<label>/chances.json` and prints a table sorted by expected points with columns `Team | Pts(exp) | Top 8 | Top 24 | R16 | QF | SF | Final | Win`.

- [ ] **Step 1: Write the failing tests** on a synthetic 36-team season.
  - Σ top8 = 8 ± 1e-9; Σ top24 = 24; Σ winner = 1; Σ over teams of `position[k]` = 1 for every k.
  - **Fixed results are never resampled:** with all 144 fixtures played, every team's `position` is one-hot and identical across seeds.
  - An override turns an unplayed fixture into a fixed result. Test: a team given 8 overridden wins in a season where nobody else can reach 24 points → `top8 === 1`.
  - Same seed → identical result; 2,000 runs complete in under 2 s.
- [ ] **Step 2: Run** `pnpm --filter @uclpred/sim test -- tests/simulate.test.ts`. Expected: FAIL. **Step 3: Implement.** **Step 4: Run** `pnpm --filter @uclpred/sim test`. Expected: all sim tests PASS.
- [ ] **Step 5: First real run.** Run the CLI for `md00` and `live` (50k runs, seed 1).
  Expected:
  - both finish; the sums printed by a footer check line are Top 8 = 8.00, Top 24 = 24.00, Win = 1.00;
  - favourites look plausible, and every probability in md00 is strictly between 0 and 1.
  Save both tables plus the as-of dates and run time in `reports/m1-first-run.md`.
- [ ] **Step 6: Commit** — `feat(sim): tournament simulation and CLI; first pre-season and live run`

---

### Task 14: Skill updates, README and full verification

**Files:**
- Modify: `.claude/skills/ingesting-football-data/SKILL.md`, `.claude/skills/modeling-match-outcomes/SKILL.md`, `.claude/skills/applying-ucl-format-rules/SKILL.md`, `.claude/skills/backtesting-predictions/SKILL.md`, `README.md`

- [ ] **Step 1: Update the skills to match the spec's "Skill updates" section.**
  - **Sources:** football-data.org + openfootball + UEFA coefficients. ClubElo and football-data.co.uk are removed, with the terms notes added.
  - **Modeling:** own Elo (`elo.py`), the GLM baseline formula and `elo-dc-v1`.
  - **Format rules:** the 2026/27 final at Atlético's ground (`finalVenueTeamId`).
  - **Backtesting:** no odds benchmark in v1.
  Keep each SKILL.md under ~550 words.
- [ ] **Step 2: Expand the README** with how to run each command (`uclpred ingest | coefficients | coverage | export`, the `sim cli`), the data sources and licences (openfootball CC0; football-data.org attribution), and a link to the spec and `reports/`.
- [ ] **Step 3: Full verification** (superpowers:verification-before-completion). Run:
  - `cd pipeline && uv run ruff check . && uv run pytest && uv run pytest -m data`
  - `pnpm --filter @uclpred/sim test`
  - `pnpm --filter @uclpred/sim exec tsc --noEmit`
  Expected: all green. Paste the summary lines into the commit body.
- [ ] **Step 4: Commit** — `docs: update skills and README for milestone 1`

---

### Task 15: Publish to GitHub

- [ ] **Step 1: Confirm the public repo name with the user** (proposed `ucl-predictor`) before creating anything.
- [ ] **Step 2:** Run `gh repo create AsimanImanzade/<name> --public --source . --remote origin --push`. Verify that `git ls-remote origin main` shows the local HEAD and that `.env` is **not** in `git ls-files`.
- [ ] **Step 3:** With the user's approval, set the repository secret by piping only the value from `.env` into `gh secret set FOOTBALL_DATA_TOKEN --repo AsimanImanzade/<name>`, without echoing it. Verify with `gh secret list`, which shows the name only.
