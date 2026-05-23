import type { Product } from '@/lib/searchResults'

/** Normalize listing text for keyword / fuzzy matching (units, spacing, Cyrillic). */
export function normalizeProductSearchText(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/[^\p{L}\p{N}\s]/gu, ' ')
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/(\d)\s*(гб|gb|гигабайт|гигабайта|гигабайтов)/gi, '$1gb')
      .replace(/(\d)\s*(тб|tb|терабайт|терабайта)/gi, '$1tb')
      .replace(/(\d)\s*(мб|mb|мегабайт|мегабайта)/gi, '$1mb')
      .replace(/(\d)\s*(г|g)\b/gi, '$1g')
      .replace(/(\d)\s*(мм|mm)\b/gi, '$1mm')
      .replace(/(\d)\s*(дюйм|inch|in)\b/gi, '$1in')
      .replace(/\s+/g, '')
  )
}

export function tokenizeLocalSearchQuery(query: string): string[] {
  return query
    .trim()
    .split(/\s+/)
    .map((part) => normalizeProductSearchText(part))
    .filter((part) => part.length > 0)
}

function levenshtein(a: string, b: string): number {
  if (a === b) return 0
  if (a.length === 0) return b.length
  if (b.length === 0) return a.length

  const rows = a.length + 1
  const cols = b.length + 1
  const matrix = Array.from({ length: rows }, () => new Array<number>(cols).fill(0))

  for (let i = 0; i < rows; i++) matrix[i][0] = i
  for (let j = 0; j < cols; j++) matrix[0][j] = j

  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1
      matrix[i][j] = Math.min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + cost)
    }
  }

  return matrix[a.length][b.length]
}

function maxEditDistance(token: string): number {
  if (token.length <= 3) return 0
  if (token.length <= 6) return 1
  return 2
}

function tokenMatchesHaystack(haystack: string, token: string): boolean {
  if (haystack.includes(token)) return true

  const maxDist = maxEditDistance(token)
  if (maxDist === 0) return false

  for (let size = Math.max(1, token.length - maxDist); size <= token.length + maxDist; size++) {
    for (let i = 0; i + size <= haystack.length; i++) {
      if (levenshtein(haystack.slice(i, i + size), token) <= maxDist) return true
    }
  }

  return false
}

function productSearchHaystack(product: Product): string {
  const parts = [product.name, product.brand].filter((part): part is string => Boolean(part?.trim()))
  return normalizeProductSearchText(parts.join(' '))
}

function matchScore(haystack: string, tokens: string[]): number {
  let score = 0
  for (const token of tokens) {
    const idx = haystack.indexOf(token)
    if (idx >= 0) {
      score += 10 + Math.max(0, 5 - idx)
      continue
    }
    if (tokenMatchesHaystack(haystack, token)) {
      score += 4
      continue
    }
    return 0
  }
  return score
}

/** All query tokens must match name/brand (substring or light fuzzy). Higher score = better fit. */
export function filterProductsByLocalSearch(products: Product[], query: string): Product[] {
  const tokens = tokenizeLocalSearchQuery(query)
  if (tokens.length === 0) return products

  return products
    .map((product) => {
      const haystack = productSearchHaystack(product)
      const score = matchScore(haystack, tokens)
      return score > 0 ? { product, score } : null
    })
    .filter((entry): entry is { product: Product; score: number } => entry !== null)
    .sort((a, b) => b.score - a.score)
    .map((entry) => entry.product)
}
