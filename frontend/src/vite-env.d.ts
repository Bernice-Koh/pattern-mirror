/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Backend base URL; unset in dev so requests stay relative behind the proxy. */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
