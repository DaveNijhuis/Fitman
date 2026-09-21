/**
 * Budget the JavaScript a visitor must download (#271).
 *
 * Vite's own "chunks are larger than 500 kB" notice is a warning, so it sat in
 * every build for months and became background noise. This is a hard gate.
 *
 * Two separate budgets, because they answer different questions:
 *
 *   entry  — what blocks first paint. Everyone downloads it, including someone
 *            opening the login page on mobile data. This is the number that
 *            matters and it is kept tight.
 *   chunk  — a ceiling on any single lazy chunk, so one route cannot quietly
 *            become enormous. Looser: nobody pays for it unless they navigate
 *            there.
 *
 * The entry chunk is read from dist/index.html rather than assumed to be the
 * largest file — after code splitting it usually is not.
 */
import { gzipSync } from 'node:zlib'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const DIST = join(import.meta.dirname, '..', 'dist')
const ASSETS = join(DIST, 'assets')

const MAX_ENTRY_GZIP_KB = 110
const MAX_CHUNK_GZIP_KB = 150

const sizes = file => {
  const raw = readFileSync(join(ASSETS, file))
  return { file, rawKb: raw.length / 1024, gzipKb: gzipSync(raw).length / 1024 }
}

const chunks = readdirSync(ASSETS)
  .filter(f => f.endsWith('.js'))
  .map(sizes)
  .sort((a, b) => b.gzipKb - a.gzipKb)

if (chunks.length === 0) {
  console.error('No JS chunks found in dist/assets — run `npm run build` first.')
  process.exit(1)
}

const html = readFileSync(join(DIST, 'index.html'), 'utf-8')
const entryMatch = html.match(/src="\/assets\/([^"]+\.js)"/)
if (!entryMatch) {
  console.error('Could not find the entry script in dist/index.html.')
  process.exit(1)
}
const entry = chunks.find(c => c.file === entryMatch[1])
if (!entry) {
  console.error(`Entry ${entryMatch[1]} referenced by index.html is not in dist/assets.`)
  process.exit(1)
}

for (const c of chunks.slice(0, 6)) {
  const tag = c.file === entry.file ? ' <- entry' : ''
  console.log(
    `  ${c.gzipKb.toFixed(1).padStart(7)} kB gzip  ${c.rawKb.toFixed(1).padStart(8)} kB raw  ${c.file}${tag}`,
  )
}
console.log(`  ${chunks.length} chunk(s) total`)

const failures = []

if (entry.gzipKb > MAX_ENTRY_GZIP_KB) {
  failures.push(
    `Entry chunk ${entry.file} is ${entry.gzipKb.toFixed(1)} kB gzipped, over the ` +
      `${MAX_ENTRY_GZIP_KB} kB budget. Everyone downloads this before anything ` +
      'renders. Check whether a route that should be lazily loaded is imported ' +
      'eagerly, or a heavy dependency reached a module the entry pulls in.',
  )
}

const oversized = chunks.filter(c => c.gzipKb > MAX_CHUNK_GZIP_KB)
for (const c of oversized) {
  failures.push(
    `Chunk ${c.file} is ${c.gzipKb.toFixed(1)} kB gzipped, over the ` +
      `${MAX_CHUNK_GZIP_KB} kB per-chunk ceiling.`,
  )
}

if (failures.length > 0) {
  console.error('\n' + failures.join('\n'))
  process.exit(1)
}

console.log(
  `\nEntry ${entry.gzipKb.toFixed(1)} kB gzipped (budget ${MAX_ENTRY_GZIP_KB} kB), ` +
    `largest chunk ${chunks[0].gzipKb.toFixed(1)} kB (ceiling ${MAX_CHUNK_GZIP_KB} kB).`,
)
