# Ingestion details

Part of `ingesting-football-data`.

6. **Alias CSV.** Keys are FIFA codes plus the exact `core_name()` output. Curation checklist: look for duplicate candidates (abbreviations, accents), check each of the 36 teams has domestic matches in >= 3 of the last 5 seasons (a split history silently weakens Elo), never merge distinct clubs (FC vs UE Santa Coloma), and keep reserve sides as separate clubs. Gaps upstream (no be/tr/gr domestic files for some seasons) are accepted, not aliased away.
7. **Fail loud.** Any non-404 fetch error raises after the loop; a silently missing competition-season corrupts Elo.
8. **Year-less dates** (openfootball TXT): infer from the season, not from the previous date. Season "YYYY-YY": Jul-Dec is YYYY, Jan-Jun is YYYY+1. A Jul/Aug date gets YYYY+1 only if the file already produced a spring (YYYY+1) date, since qualifiers open files in Jul/Aug. Explicit years always win.
9. **90-minute goals only.** football-data `fullTime` includes shoot-out goals. Use `regularTime` for 90 minutes, `regularTime + extraTime` for the ET score, `penalties` for the shoot-out. openfootball a.e.t. scores with a missing parenthesis give None, never the ET score.
10. **Undetermined fixtures** (null team ids, knockout rounds before the draw) are skipped. A non-null id missing from the team map raises.
11. **Not a gap:** 2019-20 had single-leg QF/SF after Covid (119 CL matches, not 125).
