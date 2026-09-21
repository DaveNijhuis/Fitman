import type { Measurement } from '../api/measurements'
import type { ExchangeRequest, ExchangeResponse } from '../api/scale'
import {
  FFB0, FFB1, FFB2, FFB3,
  type BluetoothLike, type GattCharacteristic, type ValueChangedEvent,
} from './bluetooth'

/**
 * The phone's side of a weigh-in (#322): relay every frame the scale sends to
 * the backend, and write what comes back to the scale, in order.
 *
 * The protocol lives in the backend (#319, #323); this only moves bytes,
 * carries the handshake state between calls, and knows when to stop. Loaded
 * on demand, so it adds nothing to the bundle for anyone who never weighs in.
 */

export type ExchangeFn = (body: ExchangeRequest) => Promise<ExchangeResponse>

export interface WeighInOptions {
  bluetooth: BluetoothLike
  exchange: ExchangeFn
  onLiveWeight?: (kg: number) => void
  /** The phone's offset from UTC, for the scale's clock. */
  utcOffsetMin?: number
  /** How long to wait for the scale's hello before starting unprompted. */
  helloWaitMs?: number
  timeoutMs?: number
}

const toHex = (view: DataView) =>
  [...new Uint8Array(view.buffer, view.byteOffset, view.byteLength)]
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')

const fromHex = (hex: string) =>
  new Uint8Array((hex.match(/../g) ?? []).map(h => parseInt(h, 16)))

/** Live weight from a 12-byte FFB2 notification; bit 0 of byte 7 is weight bit 16. */
function liveWeight(view: DataView): number | null {
  if (view.byteLength !== 12) return null
  return (((view.getUint8(7) & 1) << 16) | (view.getUint8(8) << 8) | view.getUint8(9)) / 1000
}

export async function weighIn(options: WeighInOptions): Promise<Measurement> {
  const {
    bluetooth, exchange, onLiveWeight,
    utcOffsetMin = 0, helloWaitMs = 1500, timeoutMs = 120_000,
  } = options

  let device
  try {
    device = await bluetooth.requestDevice({
      filters: [{ namePrefix: 'e.volve' }],
      optionalServices: [FFB0],
    })
  } catch (err) {
    if (err instanceof Error && err.name === 'NotFoundError') {
      throw new Error('No scale selected.', { cause: err })
    }
    throw err
  }
  const gatt = device.gatt
  if (!gatt) throw new Error('This device cannot be connected to.')

  return new Promise<Measurement>((resolve, reject) => {
    let settled = false
    let heardFromScale = false
    let state = { phone_seq: 0, sequence_sent: false }
    let queue: Promise<void> = Promise.resolve()
    let ffb1: GattCharacteristic | null = null
    const timers: ReturnType<typeof setTimeout>[] = []

    const finish = (settle: () => void) => {
      if (settled) return
      settled = true
      timers.forEach(clearTimeout)
      if (gatt.connected) gatt.disconnect()
      settle()
    }
    const fail = (err: unknown) =>
      finish(() => reject(err instanceof Error ? err : new Error(String(err))))

    // One exchange at a time: each carries the state the previous one returned,
    // and its frames must reach the scale before the next scale frame is sent on.
    const relay = async (frames: string[]) => {
      const resp = await exchange({ frames, ...state, utc_offset_min: utcOffsetMin })
      state = { phone_seq: resp.phone_seq, sequence_sent: resp.sequence_sent }
      for (const frame of resp.send) await ffb1?.writeValueWithResponse(fromHex(frame))
      if (resp.measurement) {
        const measurement = resp.measurement
        finish(() => resolve(measurement))
      } else if (resp.error) {
        fail(new Error(resp.error))
      }
    }
    const enqueue = (frames: string[]) => {
      queue = queue.then(() => (settled ? undefined : relay(frames))).catch(fail)
    }

    device.addEventListener('gattserverdisconnected', () =>
      fail(new Error('Lost connection to the scale. Step on it to wake it, then try again.')))
    timers.push(setTimeout(
      () => fail(new Error('No reading from the scale. Step on barefoot, hold the handle, and try again.')),
      timeoutMs,
    ))

    void (async () => {
      const server = await gatt.connect()
      const service = await server.getPrimaryService(FFB0)
      ffb1 = await service.getCharacteristic(FFB1)
      const ffb2 = await service.getCharacteristic(FFB2)
      const ffb3 = await service.getCharacteristic(FFB3)
      ffb2.addEventListener('characteristicvaluechanged', (e: ValueChangedEvent) => {
        const kg = liveWeight(e.target.value)
        if (kg !== null) onLiveWeight?.(kg)
      })
      ffb3.addEventListener('characteristicvaluechanged', (e: ValueChangedEvent) => {
        heardFromScale = true
        enqueue([toHex(e.target.value)])
      })
      await ffb2.startNotifications()
      await ffb3.startNotifications()
      // The hello may have gone out before we subscribed; then start unprompted.
      timers.push(setTimeout(() => { if (!heardFromScale) enqueue([]) }, helloWaitMs))
    })().catch(fail)
  })
}
