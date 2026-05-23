import createFetchClient from 'openapi-fetch'
import * as searchTypes from './types.ts'

export type { searchTypes }
export * from './events'
export * from './stream'

/** OpenAPI client for non-stream search endpoints (if added later). */
export const searchFetch = createFetchClient<searchTypes.paths>({
  baseUrl: import.meta.env.VITE_SEARCH_API_URL ?? '/search-api',
})
