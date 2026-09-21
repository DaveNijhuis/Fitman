/**
 * The slice of Web Bluetooth the scale relay uses (#322).
 *
 * TypeScript's DOM library doesn't include Web Bluetooth, and a dependency
 * for five methods isn't worth it. Only Chromium browsers and Bluefy (on iOS)
 * implement it; Safari, other iOS browsers and Firefox don't.
 */

export const FFB0 = '0000ffb0-0000-1000-8000-00805f9b34fb'  // the scale's service
export const FFB1 = '0000ffb1-0000-1000-8000-00805f9b34fb'  // write: frames to the scale
export const FFB2 = '0000ffb2-0000-1000-8000-00805f9b34fb'  // notify: live weight
export const FFB3 = '0000ffb3-0000-1000-8000-00805f9b34fb'  // indicate: frames from the scale
export const FFB4 = '0000ffb4-0000-1000-8000-00805f9b34fb'  // write without response: name image (#324)

export interface ValueChangedEvent {
  target: { value: DataView }
}

export interface GattCharacteristic {
  startNotifications(): Promise<unknown>
  addEventListener(type: 'characteristicvaluechanged', listener: (event: ValueChangedEvent) => void): void
  writeValueWithResponse(value: BufferSource): Promise<void>
  writeValueWithoutResponse(value: BufferSource): Promise<void>
}

export interface GattService {
  getCharacteristic(uuid: string): Promise<GattCharacteristic>
}

export interface GattServer {
  readonly connected: boolean
  connect(): Promise<GattServer>
  disconnect(): void
  getPrimaryService(uuid: string): Promise<GattService>
}

export interface ScaleDevice {
  gatt?: GattServer
  addEventListener(type: 'gattserverdisconnected', listener: () => void): void
}

export interface RequestDeviceOptions {
  filters: { namePrefix: string }[]
  optionalServices: string[]
}

export interface BluetoothLike {
  requestDevice(options: RequestDeviceOptions): Promise<ScaleDevice>
}

/** The browser's Web Bluetooth, or null where it doesn't exist. */
export function getBluetooth(): BluetoothLike | null {
  return (navigator as Navigator & { bluetooth?: BluetoothLike }).bluetooth ?? null
}
