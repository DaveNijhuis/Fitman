import type { components } from './schema'
import { request } from './client'

/** Optional features this instance has switched on (#326). */
export type Features = components['schemas']['FeaturesOut']

export function getFeatures(): Promise<Features> {
  return request<Features>('/api/features')
}
