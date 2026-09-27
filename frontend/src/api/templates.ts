import type { components } from './schema'
import { request } from './client'

/** A training day: built-in (Push A…) or the user's own (#354, #359). */
export type Template = components['schemas']['TemplateOut']
/** A template with its exercises, in order. */
export type TemplateDetail = components['schemas']['TemplateDetail']
export type TemplateIn = components['schemas']['TemplateIn']
export type TemplateUpdate = components['schemas']['TemplateUpdate']

export function getTemplates(): Promise<Template[]> {
  return request<Template[]>('/api/templates')
}

export function getTemplate(id: number): Promise<TemplateDetail> {
  return request<TemplateDetail>(`/api/templates/${id}`)
}

export function createTemplate(body: TemplateIn): Promise<TemplateDetail> {
  return request<TemplateDetail>('/api/templates', { method: 'POST', body: JSON.stringify(body) })
}

export function updateTemplate(id: number, body: TemplateUpdate): Promise<TemplateDetail> {
  return request<TemplateDetail>(`/api/templates/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
}

/** Its past workouts keep their name and exercise list. */
export function deleteTemplate(id: number): Promise<void> {
  return request<void>(`/api/templates/${id}`, { method: 'DELETE' })
}

/** An editable copy of any day, built-in or your own. */
export function duplicateTemplate(id: number): Promise<TemplateDetail> {
  return request<TemplateDetail>(`/api/templates/${id}/duplicate`, { method: 'POST' })
}

/** Hide a built-in from Home and the picker, or show it again. */
export function setTemplateHidden(id: number, hidden: boolean): Promise<Template> {
  return request<Template>(`/api/templates/${id}/hidden`, { method: 'PUT', body: JSON.stringify({ hidden }) })
}
