const NAMED_ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: '\u00A0',
}

/** Decodes `&amp;`, `&#47;`, `&#x2F;`, etc. from marketplace API strings. */
export function decodeHtmlEntities(value: string): string {
  if (!value.includes('&')) return value

  return value.replace(/&(#(?:x([0-9a-fA-F]+)|([0-9]+))|([a-zA-Z]+));/g, (match, _group, hex: string | undefined, dec: string | undefined, name: string | undefined) => {
    if (hex !== undefined) {
      const code = Number.parseInt(hex, 16)
      return Number.isFinite(code) ? String.fromCodePoint(code) : match
    }
    if (dec !== undefined) {
      const code = Number.parseInt(dec, 10)
      return Number.isFinite(code) ? String.fromCodePoint(code) : match
    }
    if (name) {
      return NAMED_ENTITIES[name.toLowerCase()] ?? match
    }
    return match
  })
}
