export const CORRECTED_QUERY = 'беспроводная мышь'

export type QueryCorrection = {
  displayedQuery: string
  userQuery: string
}

export function getQueryCorrection(q: string, strict: boolean, enabled = true): QueryCorrection | null {
  const userQuery = q.trim()
  if (!enabled || !userQuery || strict) return null
  if (userQuery.toLowerCase() === CORRECTED_QUERY.toLowerCase()) return null
  return { displayedQuery: CORRECTED_QUERY, userQuery }
}

export function getResultsQuery(q: string, strict: boolean, enabled = true) {
  const correction = getQueryCorrection(q, strict, enabled)
  return correction?.displayedQuery ?? q.trim()
}
