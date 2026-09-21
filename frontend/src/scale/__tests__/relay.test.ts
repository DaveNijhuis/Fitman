import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { weighIn, type ExchangeFn } from '../relay'
import { FFB0, FFB1, FFB2, FFB3 } from '../bluetooth'

/**
 * The phone's side of a weigh-in (#322): relay every frame the scale sends to
 * the backend (POST /api/scale/exchange, #323) and write whatever comes back
 * to FFB1, in order, one at a time. The protocol lives in the backend; this
 * only moves bytes, carries the handshake state, and knows when to stop.
 */

const HELLO = '0a001e00aa'
const RESULT_FRAME = '11002600a7'

type Listener = (event: { target: { value: DataView } }) => void

class FakeCharacteristic {
  written: string[] = []
  private listeners: Listener[] = []
  notifying = false
  readonly uuid: string
  private log: string[]
  constructor(uuid: string, log: string[]) {
    this.uuid = uuid
    this.log = log
  }
  async startNotifications() {
    this.notifying = true
    return this
  }
  addEventListener(_type: string, fn: Listener) {
    this.listeners.push(fn)
  }
  async writeValueWithResponse(data: BufferSource) {
    const bytes = new Uint8Array(data instanceof ArrayBuffer ? data : (data as ArrayBufferView).buffer)
    const hex = [...bytes].map(b => b.toString(16).padStart(2, '0')).join('')
    this.written.push(hex)
    this.log.push(`write ${hex}`)
  }
  emit(hex: string) {
    const bytes = new Uint8Array(hex.match(/../g)!.map(h => parseInt(h, 16)))
    for (const fn of this.listeners) fn({ target: { value: new DataView(bytes.buffer) } })
  }
}

function fakeScale() {
  const log: string[] = []
  const chars = new Map([FFB1, FFB2, FFB3].map(u => [u, new FakeCharacteristic(u, log)]))
  const deviceListeners: Record<string, (() => void)[]> = {}
  const gatt = {
    connected: false,
    async connect() { gatt.connected = true; return gatt },
    disconnect: vi.fn(() => { gatt.connected = false }),
    async getPrimaryService(uuid: string) {
      expect(uuid).toBe(FFB0)
      return { getCharacteristic: async (u: string) => chars.get(u)! }
    },
  }
  const device = {
    name: 'e.volve-10765',
    gatt,
    addEventListener: (type: string, fn: () => void) => { (deviceListeners[type] ??= []).push(fn) },
  }
  const requestDevice = vi.fn(async () => device)
  return {
    bluetooth: { requestDevice },
    requestDevice,
    gatt,
    log,
    ffb1: chars.get(FFB1)!,
    ffb2: chars.get(FFB2)!,
    ffb3: chars.get(FFB3)!,
    dropConnection: () => deviceListeners['gattserverdisconnected']?.forEach(fn => fn()),
  }
}

const MEASUREMENT = { id: 7, weight_kg: 72.5, body_fat_pct: 18.5 } as never

/** Flush queued promise work (the relay is a chain of awaits). */
async function settle() {
  for (let i = 0; i < 20; i++) await Promise.resolve()
}

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('connecting', () => {
  it('asks the browser for an e.volve scale with the FFB0 service', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({ send: [], phone_seq: 0, sequence_sent: false, measurement: null, error: null }))
    void weighIn({ bluetooth: s.bluetooth, exchange }).catch(() => {})
    await settle()
    expect(s.requestDevice).toHaveBeenCalledWith({
      filters: [{ namePrefix: 'e.volve' }],
      optionalServices: [FFB0],
    })
    expect(s.ffb2.notifying && s.ffb3.notifying).toBe(true)
  })
})

describe('relaying', () => {
  it('posts each scale frame and writes the returned frames to FFB1 in order', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({
      send: ['aa01', 'bb02', 'cc03'], phone_seq: 6, sequence_sent: true, measurement: null, error: null,
    }))
    void weighIn({ bluetooth: s.bluetooth, exchange, utcOffsetMin: 120 }).catch(() => {})
    await settle()
    s.ffb3.emit(HELLO)
    await settle()
    expect(exchange).toHaveBeenCalledWith({
      frames: [HELLO], phone_seq: 0, sequence_sent: false, utc_offset_min: 120,
    })
    expect(s.ffb1.written).toEqual(['aa01', 'bb02', 'cc03'])
  })

  it('carries the handshake state into the next exchange', async () => {
    const s = fakeScale()
    const exchange = vi.fn<ExchangeFn>()
      .mockResolvedValueOnce({ send: ['aa01'], phone_seq: 6, sequence_sent: true, measurement: null, error: null })
      .mockResolvedValue({ send: [], phone_seq: 6, sequence_sent: true, measurement: null, error: null })
    void weighIn({ bluetooth: s.bluetooth, exchange, utcOffsetMin: 0 }).catch(() => {})
    await settle()
    s.ffb3.emit(HELLO)
    await settle()
    s.ffb3.emit('04000300a0010001')
    await settle()
    expect(exchange.mock.calls[1]![0]).toMatchObject({ phone_seq: 6, sequence_sent: true })
  })

  it('handles one frame at a time, even when the scale sends two quickly', async () => {
    const s = fakeScale()
    let release!: () => void
    const exchange = vi.fn<ExchangeFn>()
      .mockImplementationOnce(() => new Promise(r => {
        release = () => r({ send: ['aa01'], phone_seq: 6, sequence_sent: true, measurement: null, error: null })
      }))
      .mockResolvedValue({ send: [], phone_seq: 6, sequence_sent: true, measurement: null, error: null })
    void weighIn({ bluetooth: s.bluetooth, exchange }).catch(() => {})
    await settle()
    s.ffb3.emit(HELLO)
    s.ffb3.emit('04000300a0010001')
    await settle()
    expect(exchange).toHaveBeenCalledTimes(1)  // the second waits for the first
    release()
    await settle()
    expect(exchange).toHaveBeenCalledTimes(2)
    expect(s.log[0]).toBe('write aa01')  // the first's write happened before the second exchange
  })

  it('starts unprompted when no hello arrives', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({ send: [], phone_seq: 5, sequence_sent: true, measurement: null, error: null }))
    void weighIn({ bluetooth: s.bluetooth, exchange }).catch(() => {})
    await settle()
    expect(exchange).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1600)
    expect(exchange).toHaveBeenCalledWith(expect.objectContaining({ frames: [] }))
  })

  it('reports live weight from FFB2', async () => {
    const s = fakeScale()
    const onLiveWeight = vi.fn()
    const exchange: ExchangeFn = vi.fn(async () => ({ send: [], phone_seq: 0, sequence_sent: false, measurement: null, error: null }))
    void weighIn({ bluetooth: s.bluetooth, exchange, onLiveWeight }).catch(() => {})
    await settle()
    s.ffb2.emit('ba000700a20025611b340007')  // status bit 0 carries 65536 g
    expect(onLiveWeight).toHaveBeenCalledWith(72.5)
  })
})

describe('finishing', () => {
  it('resolves with the stored measurement and disconnects', async () => {
    const s = fakeScale()
    const exchange = vi.fn<ExchangeFn>()
      .mockResolvedValueOnce({ send: ['aa01'], phone_seq: 6, sequence_sent: true, measurement: null, error: null })
      .mockResolvedValue({ send: ['b006'], phone_seq: 7, sequence_sent: true, measurement: MEASUREMENT, error: null })
    const done = weighIn({ bluetooth: s.bluetooth, exchange })
    await settle()
    s.ffb3.emit(HELLO)
    await settle()
    s.ffb3.emit(RESULT_FRAME)
    await expect(done).resolves.toBe(MEASUREMENT)
    expect(s.ffb1.written).toContain('b006')  // the result's ack went out first
    expect(s.gatt.disconnect).toHaveBeenCalled()
  })

  it('rejects with the backend error, e.g. an incomplete profile, and disconnects', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => {
      throw new Error('Complete your profile before weighing in: height')
    })
    const done = weighIn({ bluetooth: s.bluetooth, exchange })
    await settle()
    s.ffb3.emit(HELLO)
    await expect(done).rejects.toThrow('Complete your profile')
    expect(s.gatt.disconnect).toHaveBeenCalled()
  })

  it('rejects when the result was for someone else', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({
      send: ['b006'], phone_seq: 7, sequence_sent: true, measurement: null,
      error: 'The scale attributed this weigh-in to a different scale user; not stored.',
    }))
    const done = weighIn({ bluetooth: s.bluetooth, exchange })
    await settle()
    s.ffb3.emit(RESULT_FRAME)
    await expect(done).rejects.toThrow('different scale user')
    expect(s.ffb1.written).toContain('b006')  // still acknowledged, or the scale re-sends it
  })

  it('rejects when the connection drops before a result', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({ send: [], phone_seq: 0, sequence_sent: false, measurement: null, error: null }))
    const done = weighIn({ bluetooth: s.bluetooth, exchange })
    await settle()
    s.dropConnection()
    await expect(done).rejects.toThrow(/connection/i)
  })

  it('gives up with a message rather than waiting forever', async () => {
    const s = fakeScale()
    const exchange: ExchangeFn = vi.fn(async () => ({ send: [], phone_seq: 0, sequence_sent: false, measurement: null, error: null }))
    const done = weighIn({ bluetooth: s.bluetooth, exchange, timeoutMs: 5000 })
    const check = expect(done).rejects.toThrow(/no reading/i)
    await vi.advanceTimersByTimeAsync(5100)
    await check
    expect(s.gatt.disconnect).toHaveBeenCalled()
  })

  it('says so when the user closes the device chooser', async () => {
    const s = fakeScale()
    s.requestDevice.mockRejectedValueOnce(Object.assign(new Error('User cancelled'), { name: 'NotFoundError' }))
    const exchange: ExchangeFn = vi.fn()
    await expect(weighIn({ bluetooth: s.bluetooth, exchange })).rejects.toThrow(/no scale selected/i)
  })
})
