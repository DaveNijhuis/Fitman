import type { components } from './schema'

export function getToken(): string | null {
  return localStorage.getItem('token')
}

export function saveToken(token: string): void {
  localStorage.setItem('token', token)
}

export function clearToken(): void {
  localStorage.removeItem('token')
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(path, { ...options, headers })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }))
    const detail = Array.isArray(error.detail)
      ? error.detail.map((e: { msg: string }) => e.msg).join(', ')
      : (error.detail ?? 'Request failed')
    throw new Error(detail)
  }

  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

/** The envelope returned by paginated list endpoints (see #227). */
export interface Page<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/**
 * Compile-time guard that the generic envelope above still matches what the
 * backend publishes. `Page<T>` is the one API shape not generated from the
 * OpenAPI document, and it is the exact shape #267 got wrong — so if a *Page
 * schema changes, this must stop compiling rather than silently mis-reading
 * the response. Types only: erased at build, nothing reaches the bundle.
 */
type AssertAssignableToPage<T extends Page<unknown>> = T
export type _CardioPageIsAPage = AssertAssignableToPage<
  components['schemas']['CardioPage']
>
export type _MeasurementPageIsAPage = AssertAssignableToPage<
  components['schemas']['MeasurementPage']
>

/** The backend caps page_size at 200; ask for the maximum to minimise round trips. */
const MAX_PAGE_SIZE = 200

/** Safety bound: 200 × 500 = 100k records, far beyond any household instance. */
const MAX_PAGES = 500

/**
 * Collect every record from a paginated endpoint.
 *
 * Callers want the whole history — the Progress charts plot all of it, and the
 * Cardio page lists all of it. Reading only the first page would trade the
 * crash in #267 for silent truncation, which is the worse failure: charts would
 * quietly stop at the newest 50 records with nothing to indicate it.
 *
 * Paging is driven by the envelope's `total` rather than by assuming the server
 * honoured the requested `page_size`.
 */
export async function fetchAllPages<T>(path: string): Promise<T[]> {
  const collected: T[] = []
  const separator = path.includes('?') ? '&' : '?'

  for (let page = 1; page <= MAX_PAGES; page++) {
    const result = await request<Page<T>>(
      `${path}${separator}page=${page}&page_size=${MAX_PAGE_SIZE}`,
    )
    collected.push(...result.items)

    // Empty page guards against a server that reports a total it cannot serve.
    if (result.items.length === 0 || collected.length >= result.total) return collected
  }

  throw new Error(`${path}: exceeded ${MAX_PAGES} pages while collecting results`)
}
