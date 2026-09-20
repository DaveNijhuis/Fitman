import { afterEach, describe, expect, it, vi } from 'vitest'
import { getCardioHistory } from '../cardio'
import { getMeasurements } from '../measurements'

/**
 * #227 paginated GET /api/cardio and GET /api/measurements, changing both
 * responses from a bare array to { items, total, page, page_size }. The
 * clients kept declaring arrays, and `res.json() as Promise<T>` let the lie
 * compile — so ProgressPage threw and CardioPage silently rendered nothing.
 *
 * These tests drive the clients from the real response shape.
 */

type Envelope = { items: unknown[]; total: number; page: number; page_size: number }

/** Serves `total` records in pages of `pageSize`, recording each request. */
function mockPaginatedApi(total: number, pageSize: number, make: (i: number) => unknown) {
  const calls: string[] = []
  const fetchMock = vi.fn(async (url: string) => {
    calls.push(url)
    const page = Number(new URL(url, 'http://localhost').searchParams.get('page') ?? '1')
    const start = (page - 1) * pageSize
    const items = Array.from({ length: Math.max(0, Math.min(pageSize, total - start)) },
      (_, i) => make(start + i))
    const body: Envelope = { items, total, page, page_size: pageSize }
    return {
      ok: true,
      status: 200,
      json: async () => body,
    } as unknown as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls }
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const measurement = (i: number) => ({ id: i, weight_kg: 80 + i, recorded_at: '2026-01-01T00:00:00Z' })
const cardio = (i: number) => ({ id: i, activity: 'Run', distance_m: 5000, duration_s: 1800, logged_at: '2026-01-01T00:00:00Z' })

describe('getMeasurements', () => {
  it('returns an array, not the pagination envelope', async () => {
    mockPaginatedApi(3, 50, measurement)
    const result = await getMeasurements()
    expect(Array.isArray(result)).toBe(true)
    expect(result).toHaveLength(3)
  })

  it('returns usable records rather than the envelope object', async () => {
    mockPaginatedApi(1, 50, measurement)
    const [first] = await getMeasurements()
    expect(first?.weight_kg).toBe(80)
  })

  it('is iterable — ProgressPage spreads and .find()s this value', async () => {
    mockPaginatedApi(2, 50, measurement)
    const result = await getMeasurements()
    expect(() => [...result]).not.toThrow()
    expect(result.find(m => m.weight_kg != null)).toBeDefined()
  })

  it('returns every record when the history exceeds one page', async () => {
    // The regression that would otherwise replace a crash with silent truncation.
    mockPaginatedApi(120, 50, measurement)
    const result = await getMeasurements()
    expect(result).toHaveLength(120)
  })

  it('handles an empty history', async () => {
    mockPaginatedApi(0, 50, measurement)
    expect(await getMeasurements()).toEqual([])
  })
})

describe('getCardioHistory', () => {
  it('returns an array, not the pagination envelope', async () => {
    mockPaginatedApi(4, 50, cardio)
    const result = await getCardioHistory()
    expect(Array.isArray(result)).toBe(true)
    expect(result).toHaveLength(4)
  })

  it('exposes .length so CardioPage renders its history block', async () => {
    mockPaginatedApi(4, 50, cardio)
    const result = await getCardioHistory()
    expect(result.length).toBeGreaterThan(0)
  })

  it('returns every record when the history exceeds one page', async () => {
    mockPaginatedApi(75, 50, cardio)
    expect(await getCardioHistory()).toHaveLength(75)
  })

  it('stops requesting once the last page is served', async () => {
    const { calls } = mockPaginatedApi(75, 50, cardio)
    await getCardioHistory()
    expect(calls).toHaveLength(2)
  })
})
