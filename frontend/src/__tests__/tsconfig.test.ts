import { describe, expect, it } from 'vitest'
// ?raw keeps this a browser-typed module: no @types/node, and therefore no
// Node globals leaking into the app's type scope.
import raw from '../../tsconfig.app.json?raw'

/**
 * Static checks on the TypeScript compiler gate (#223).
 *
 * TypeScript 6 turns `strict` on by default, so the app already compiles
 * strictly — but only by accident of the compiler version. Declaring it
 * keeps the guarantee if TypeScript is ever pinned back, and the flags
 * beyond `strict` are the ones still finding real defects.
 */

/** tsconfig files are JSONC: strip comments before parsing. */
function readTsconfig(): { compilerOptions: Record<string, unknown> } {
  const stripped = raw
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '')
  return JSON.parse(stripped)
}

describe('tsconfig.app.json compiler gate', () => {
  const options = () => readTsconfig().compilerOptions

  it('declares strict explicitly rather than relying on the TS 6 default', () => {
    expect(options().strict).toBe(true)
  })

  it('enables noUncheckedIndexedAccess', () => {
    // Index access returns T, not T | undefined, without this.
    expect(options().noUncheckedIndexedAccess).toBe(true)
  })

  it('enables exactOptionalPropertyTypes', () => {
    // Distinguishes "absent" from "present and undefined" in props.
    expect(options().exactOptionalPropertyTypes).toBe(true)
  })

  it('enables noImplicitOverride', () => {
    // Catches lifecycle methods that silently stop overriding the base class.
    expect(options().noImplicitOverride).toBe(true)
  })
})
