/** Crest kill switch: VITE_SHOW_CRESTS=false swaps every crest for a colour chip + short code. */
export const SHOW_CRESTS: boolean = import.meta.env.VITE_SHOW_CRESTS !== 'false';

/** Live-score Worker (`live/`). VITE_LIVE_URL overrides it; an empty value turns live scores off. */
export const LIVE_URL: string = import.meta.env.VITE_LIVE_URL ?? 'https://ucl-predictor-live.asimanimanzade2005.workers.dev/';
