/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "false" swaps every crest for a colour chip + short code. Default: crests on. */
  readonly VITE_SHOW_CRESTS?: string;
  /** Live-score Worker URL; empty turns live scores off. */
  readonly VITE_LIVE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
