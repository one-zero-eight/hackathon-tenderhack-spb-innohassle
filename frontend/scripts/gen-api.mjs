#!/usr/bin/env node
import { writeFileSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import http from 'node:http'
import https from 'node:https'

const frontendRoot = join(dirname(fileURLToPath(import.meta.url)), '..')
const apiPort = process.env.API_PORT || '8000'
const caddyPort = process.env.CADDY_PORT || '9443'

/** @type {{ url: string; insecure?: boolean }[]} */
const defaultCandidates = [
  { url: `http://127.0.0.1:${apiPort}/openapi.json` },
  { url: `http://localhost:${apiPort}/openapi.json` },
  { url: `https://127.0.0.1:${caddyPort}/api/openapi.json`, insecure: true },
  { url: `https://localhost:${caddyPort}/api/openapi.json`, insecure: true },
]

function fetchSpec(url, { insecure = false } = {}) {
  return new Promise((resolve, reject) => {
    const lib = url.startsWith('https:') ? https : http
    const req = lib.get(url, insecure ? { rejectUnauthorized: false } : undefined, (res) => {
      if (res.statusCode && res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        fetchSpec(res.headers.location, { insecure }).then(resolve).catch(reject)
        return
      }
      if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 300) {
        reject(new Error(`${res.statusCode ?? 'unknown'} ${res.statusMessage ?? ''}`.trim()))
        res.resume()
        return
      }
      const chunks = []
      res.on('data', (chunk) => chunks.push(chunk))
      res.on('end', () => {
        try {
          resolve(JSON.parse(Buffer.concat(chunks).toString('utf8')))
        } catch (err) {
          reject(err)
        }
      })
    })
    req.on('error', reject)
    req.setTimeout(10_000, () => req.destroy(new Error('timeout')))
  })
}

async function resolveSpec() {
  const explicit = process.env.OPENAPI_SPEC_URL?.trim()
  if (explicit) {
    const insecure = explicit.startsWith('https://')
    try {
      return { url: explicit, spec: await fetchSpec(explicit, { insecure }) }
    } catch (err) {
      throw new Error(`OPENAPI_SPEC_URL (${explicit}): ${err.message}`)
    }
  }

  const errors = []
  for (const candidate of defaultCandidates) {
    try {
      const spec = await fetchSpec(candidate.url, candidate)
      return { url: candidate.url, spec }
    } catch (err) {
      errors.push(`${candidate.url} — ${err.message}`)
    }
  }

  throw new Error(
    [
      'Could not fetch OpenAPI spec. Start the API (e.g. docker compose up) and retry.',
      '',
      'Tried:',
      ...errors.map((line) => `  • ${line}`),
      '',
      'Override with OPENAPI_SPEC_URL, e.g.:',
      `  OPENAPI_SPEC_URL=http://127.0.0.1:${apiPort}/openapi.json pnpm gen:api`,
    ].join('\n'),
  )
}

function fixHeaders(obj) {
  if (!obj || typeof obj !== 'object') return
  if (Array.isArray(obj)) {
    obj.forEach(fixHeaders)
    return
  }
  for (const key of Object.keys(obj)) {
    if (key === 'headers' && typeof obj[key] === 'object') {
      const headers = obj[key]
      for (const [name, value] of Object.entries(headers)) {
        if (typeof value === 'string') {
          headers[name] = {
            description: value,
            schema: { type: 'string', example: value },
          }
        }
      }
    } else {
      fixHeaders(obj[key])
    }
  }
}

const { url: specUrl, spec } = await resolveSpec()
console.log(`Using OpenAPI spec from ${specUrl}`)

fixHeaders(spec)

const tmpDir = mkdtempSync(join(tmpdir(), 'openapi-'))
const tmpFile = join(tmpDir, 'openapi.json')
try {
  writeFileSync(tmpFile, JSON.stringify(spec, null, 2))
  const result = spawnSync('pnpm', ['exec', 'openapi-typescript', tmpFile, '--output', 'src/api/types.ts', '--root-types', '--enum'], { stdio: 'inherit', cwd: frontendRoot })
  process.exit(result.status ?? 1)
} finally {
  rmSync(tmpDir, { recursive: true })
}
