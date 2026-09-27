import type { components } from './schema'
import { request } from './client'

/** A training day: built-in (Push A…) or the user's own (#354). */
export type Template = components['schemas']['TemplateOut']
/** A template with its exercises, in order. */
export type TemplateDetail = components['schemas']['TemplateDetail']

export function getTemplates(): Promise<Template[]> {
  return request<Template[]>('/api/templates')
}

export function getTemplate(id: number): Promise<TemplateDetail> {
  return request<TemplateDetail>(`/api/templates/${id}`)
}
