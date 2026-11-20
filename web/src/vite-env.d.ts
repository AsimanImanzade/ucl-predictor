/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "false" swaps every crest for a colour chip + short code. Default: crests on. */
  readonly VITE_SHOW_CRESTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
