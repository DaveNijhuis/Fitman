import { describe, expect, it } from 'vitest'
// ?raw keeps this a browser-typed module: no @types/node needed in the app scope.
import schema from '../schema.d.ts?raw'
import cardioSource from '../cardio.ts?raw'
import measurementsSource from '../measurements.ts?raw'

/**
 * The API layer must derive its response types from the backend's published
 * OpenAPI schema rather than hand-written interfaces (#268).
 *
 * client.ts casts with `res.json() as Promise<T>`, so a hand-written interface
 * is never checked against anything. #227 changed two response shapes, all 34
 * call sites kept compiling, and #267 followed.
 */

describe('generated schema', () => {
  it('exists and is generated from the OpenAPI document', () => {
    expect(schema.length).toBeGreaterThan(0)
    expect(schema).toContain('components')
  })

  it('carries the paginated envelopes that #267 tripped over', () => {
    expect(schema).toContain('CardioPage')
    expect(schema).toContain('MeasurementPage')
  })

  it('describes the endpoints the app calls', () => {
    expect(schema).toContain('/api/cardio')
    expect(schema).toContain('/api/measurements')
  })
})

describe('API modules', () => {
  it('cardio derives its types from the generated schema', () => {
    expect(cardioSource).toMatch(/from '\.\/schema/)
  })

  it('measurements derives its types from the generated schema', () => {
    expect(measurementsSource).toMatch(/from '\.\/schema/)
  })

  it('cardio does not hand-declare its response shape', () => {
    expect(cardioSource).not.toMatch(/^export interface CardioEntry \{/m)
  })

  it('measurements does not hand-declare its response shape', () => {
    expect(measurementsSource).not.toMatch(/^export interface Measurement \{/m)
  })
})
