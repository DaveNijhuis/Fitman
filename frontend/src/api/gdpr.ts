import { request, getToken } from './client'

export async function exportData(): Promise<void> {
  const token = getToken()
  const res = await fetch('/api/gdpr/export', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const filename = disposition.match(/filename="(.+)"/)?.[1] ?? 'fitman-data.json'
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

export function eraseAccount(): Promise<void> {
  return request<void>('/api/gdpr/erase', { method: 'DELETE' })
}
