/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_POSTGREST_URL?: string;
  /** Supabase project anon key. Unset for a self-hosted PostgREST. */
  readonly VITE_SUPABASE_ANON_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
