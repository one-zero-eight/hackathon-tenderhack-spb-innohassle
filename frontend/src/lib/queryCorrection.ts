export type QueryCorrection = {
  displayedQuery: string
  userQuery: string
}

export function getQueryCorrection(userQuery: string, fixedQuery: string | null | undefined, strict: boolean): QueryCorrection | null {
  const trimmedUserQuery = userQuery.trim()
  if (strict || !trimmedUserQuery) return null

  const trimmedFixedQuery = fixedQuery?.trim()
  if (!trimmedFixedQuery) return null
  if (trimmedFixedQuery.toLowerCase() === trimmedUserQuery.toLowerCase()) return null

  return { displayedQuery: trimmedFixedQuery, userQuery: trimmedUserQuery }
}
