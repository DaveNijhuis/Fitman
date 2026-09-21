import type { components } from './schema'
import { request } from './client'

/**
 * The smart scale relay (#323). The backend owns the protocol: each call
 * carries the frames the scale sent plus the handshake state the phone keeps,
 * and returns the frames to write back to the scale.
 */
export type ExchangeRequest = Required<components['schemas']['ExchangeIn']>
export type ExchangeResponse = components['schemas']['ExchangeOut']

export function exchangeScale(body: ExchangeRequest): Promise<ExchangeResponse> {
  return request<ExchangeResponse>('/api/scale/exchange', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
