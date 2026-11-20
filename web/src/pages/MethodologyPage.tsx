import { use } from 'react';
import { Link } from 'react-router';
import { CalibrationChart, type CalibrationBin } from '../components/Charts';
import { seasonAccuracy } from '../lib/accuracy';
import { useAllSnapshots, useManifest, useSnapshot } from '../lib/data';
import { formatDate } from '../lib/labels';
import './pages.css';
import './MethodologyPage.css';

interface Calibration {
  model: string;
  scope: string;
  n: number;
  bins: CalibrationBin[];
}

let calibration: Promise<Calibration | null> | null = null;
const loadCalibration = () =>
  (calibration ??= fetch('/data/calibration.json')
    .then((r) => (r.ok ? (r.json() as Promise<Calibration>) : null))
    .catch(() => null));

const SETTINGS: [string, string][] = [
  ['Elo K factor', '24'],
  ['Extra weight on European matches (K multiplier)', '2.0'],
  ['League-level gain from cross-league results (g)', '0.9'],
  ['Home advantage', '60 Elo points'],
  ['Goals model ridge penalty (alpha)', '0.005'],
  ['Time decay', '0.0019 per day (half-life about a year)'],
  ['Training window', '1,460 days'],
  ['Weight on European matches in the goals model', '2.0'],
  ['Rating uncertainty in the simulation (sigma)', '0 (ratings treated as exact)'],
];

const GATES: [string, string, string, string][] = [
  ['G1', 'League bias: mid-league clubs vs Big-5 clubs, expected-score gap', '−0.021 (v1: −0.152)', 'within ±0.03'],
  ['G2', 'European matches 2022-26 (n = 2,390): upper 95% bound of the RPS change vs v1', '+0.0028', 'at most +0.003'],
  ['G3', 'All matches since 7 Sep 2026 (n = 589): upper 95% bound of the RPS change vs v1', '+0.0032', 'at most +0.006'],
  ['G4', 'Review of the pre-season and live tables', 'Approved 10 Nov 2026', 'owner approves'],
];

const BY_COMP: [string, number, number, number][] = [
  ['Serie A', 82, 0.198, 0.2004],
  ['LaLiga', 80, 0.1727, 0.176],
  ['Champions League', 72, 0.1855, 0.1858],
  ['Premier League', 70, 0.2157, 0.2148],
  ['Eredivisie', 67, 0.2167, 0.2167],
  ['Bundesliga', 63, 0.198, 0.1981],
  ['Ligue 1', 63, 0.1936, 0.1974],
  ['Primeira Liga', 57, 0.2041, 0.2046],
  ['Championship', 35, 0.2134, 0.2149],
];

function SeasonScore() {
  const manifest = useManifest();
  const snaps = useAllSnapshots();
  const live = useSnapshot(manifest.liveId);
  const acc = seasonAccuracy(manifest, snaps, live);
  if (!acc.n) return <p>No league-phase matches have been played yet.</p>;
  return (
    <div className="kpis">
      <div className="kpi">
        <span className="kpi__value num">{acc.meanRps.toFixed(3)}</span>
        <span className="kpi__label">mean RPS over the {acc.n} matches played so far (lower is better)</span>
      </div>
      <div className="kpi">
        <span className="kpi__value num">
          {acc.favouriteRight} of {acc.n}
        </span>
        <span className="kpi__label">matches where the most likely outcome happened</span>
      </div>
    </div>
  );
}

export function MethodologyPage() {
  const manifest = useManifest();
  const cal = use(loadCalibration());
  return (
    <div className="page method">
      <header className="page-head">
        <h1>Methodology and accuracy</h1>
        <p className="lead">
          How the numbers are made, how well they have done, and where they are weak. Current model: <strong>{manifest.model}</strong>, live data as of{' '}
          {formatDate(manifest.updatedAt)}.
        </p>
      </header>

      <section className="section prose" aria-labelledby="how">
        <h2 id="how">How the forecasts work</h2>
        <ol className="steps">
          <li>
            <h3>Ratings</h3>
            <p>
              Every club gets an Elo rating built from domestic and European results since 2010. The ratings are league-aware: each
              league has a level that moves with its clubs&rsquo; results against other leagues, so a strong domestic record in a weaker league
              counts for less.
            </p>
          </li>
          <li>
            <h3>Goals</h3>
            <p>
              A Poisson goals model turns the rating gap and home advantage into expected goals for both sides, with the Dixon-Coles correction
              for low scores. Recent matches count more. This gives a full scoreline distribution for every possible pairing, at home and at a
              neutral venue.
            </p>
          </li>
          <li>
            <h3>Simulation</h3>
            <p>
              The rest of the competition is played out 50,000 times: the remaining league-phase matches, the official tiebreakers, the
              play-off and round-of-16 draws with their seeding rules, two-legged ties with extra time and penalties, and the final in Madrid at
              Atlético&rsquo;s ground (home advantage if Atlético reach it). Real results are never resampled. The{' '}
              <Link to="/what-if">What-if</Link> page runs the same simulator code in your browser, so its numbers match these.
            </p>
          </li>
        </ol>
      </section>

      <section className="section prose" aria-labelledby="coverage">
        <h2 id="coverage">Data coverage</h2>
        <p>
          All 36 clubs have European results. For 25 of them, current domestic league results come from football-data.org. The other 11 (Club
          Brugge, Bodø/Glimt, Shakhtar, Fenerbahçe, Galatasaray, LASK, AEK Athens, Slavia Praha, Sabah, Viking and Slovan Bratislava) have no
          current domestic data, so their ratings lean on European results. Como has no UEFA coefficient and counts as 0 in the last tiebreaker.
        </p>
      </section>

      <section className="section" aria-labelledby="model">
        <h2 id="model">Model settings</h2>
        <p className="fineprint section-note">Fixed before the evaluation below and not tuned afterwards.</p>
        <table className="data-table">
          <tbody>
            {SETTINGS.map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{k}</th>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="section" aria-labelledby="accuracy">
        <h2 id="accuracy">Accuracy</h2>
        <p className="prose-p">
          The ranked probability score (RPS) measures how far a home/draw/away forecast was from what happened: 0 is perfect, and lower is
          better. On the matches below, both models score between about 0.17 and 0.22.
        </p>

        <h3 className="sub">This season</h3>
        <p className="fineprint section-note">Each match is scored with the forecast published before its matchday (pre-season for matchday 1).</p>
        <SeasonScore />

        <h3 className="sub">Pre-registered gates</h3>
        <p className="fineprint section-note">
          The current model replaced the first baseline (v1) only after passing four gates written down before the single evaluation run.
        </p>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Gate</th>
                <th scope="col">Test</th>
                <th scope="col">Result</th>
                <th scope="col">Pass mark</th>
              </tr>
            </thead>
            <tbody>
              {GATES.map(([g, test, val, mark]) => (
                <tr key={g}>
                  <th scope="row">{g}</th>
                  <td>{test}</td>
                  <td className="num">{val}</td>
                  <td>{mark}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <h3 className="sub">By competition, since 7 September 2026</h3>
        <div className="table-wrap">
          <table className="data-table data-table--num">
            <thead>
              <tr>
                <th scope="col">Competition</th>
                <th scope="col">Matches</th>
                <th scope="col">RPS, v1</th>
                <th scope="col">RPS, current</th>
              </tr>
            </thead>
            <tbody>
              {BY_COMP.map(([c, n, a, b]) => (
                <tr key={c}>
                  <th scope="row">{c}</th>
                  <td>{n}</td>
                  <td>{a.toFixed(4)}</td>
                  <td>{b.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {cal && (
          <>
            <h3 className="sub">Calibration</h3>
            <p className="fineprint section-note">
              European matches 2022-26 ({cal.n.toLocaleString('en-GB')} forecasts), grouped by predicted home-win chance. Points on the diagonal
              mean the chances came true as often as stated; dot size grows with the number of matches.
            </p>
            <div className="cal-grid">
              <div className="panel">
                <CalibrationChart bins={cal.bins} />
              </div>
              <table className="data-table data-table--num">
                <thead>
                  <tr>
                    <th scope="col">Predicted</th>
                    <th scope="col">Matches</th>
                    <th scope="col">Mean forecast</th>
                    <th scope="col">Home won</th>
                  </tr>
                </thead>
                <tbody>
                  {cal.bins.map((b) => (
                    <tr key={b.lo}>
                      <th scope="row">
                        {Math.round(b.lo * 100)}&ndash;{Math.round(b.hi * 100)}%
                      </th>
                      <td>{b.n}</td>
                      <td>{b.meanPred === null ? '–' : `${(b.meanPred * 100).toFixed(1)}%`}</td>
                      <td>{b.observed === null ? '–' : `${(b.observed * 100).toFixed(1)}%`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        <h3 className="sub">Whole-tournament check</h3>
        <p className="prose-p">
          Run on the 2024-25 and 2025-26 competitions from their pre-season data, the current model scored a worse stage log loss than v1 (1.419
          against 1.358, lower is better). This check was reported but not used as a gate; it is one reason to read title chances with care.
        </p>
      </section>

      <section className="section prose" aria-labelledby="limits">
        <h2 id="limits">Known limitations</h2>
        <ul className="limits">
          <li>
            <strong>Residual league bias.</strong> Clubs from mid-ranked leagues still do slightly worse against Big-5 clubs than the model expects
            (about &minus;0.08 expected score per match, down from &minus;0.14 under v1).
          </li>
          <li>
            <strong>League-level pooling.</strong> A league&rsquo;s level moves with every cross-league European result and does not decay, so clubs
            inherit their compatriots&rsquo; European record. Lille and Lens were lifted this way before the season.
          </li>
          <li>
            <strong>Exact ratings.</strong> Ratings are treated as exact in the simulation, so title chances may be too concentrated on the
            favourites. Before the season, Bayern alone had a 24% title chance.
          </li>
          <li>
            <strong>Club level only.</strong> Injuries, transfers, suspensions and squad rotation are not modelled.
          </li>
          <li>
            <strong>Draws and discipline.</strong> Knockout draws are simulated with the official seeding rules until the real draws are made. The
            disciplinary-points tiebreaker is skipped because card data is not available.
          </li>
        </ul>
      </section>

      <section className="section prose" aria-labelledby="sources">
        <h2 id="sources">Sources</h2>
        <p>
          Historical results: openfootball (public domain). Live and recent results: football-data.org. Club coefficients: UEFA, used only as a
          tiebreaker. No betting odds are used.
        </p>
      </section>
    </div>
  );
}
