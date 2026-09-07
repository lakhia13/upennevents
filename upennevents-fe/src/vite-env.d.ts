/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_POSTGREST_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
