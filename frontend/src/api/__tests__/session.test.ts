import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getToken, request, saveToken, session } from '../client'
import { login } from '../auth'
import { exportData } from '../gdpr'

/**
 * A token the backend rejects must end the session (#317).
 *
 * The route guard only checks that a token exists, and request() reported a
 * 401 like any other failure. With an expired or re-keyed token every page
 * showed "Could not load data — please check your connection" and nothing led
 * back to the login screen. Tokens expire after 7 days by default, so every
 * user hit this weekly.
 */

type Reply = { status: number; body?: unknown }

function mockFetch(reply: Reply | Error) {
  const fetchMock = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(async () => {
    if (reply instanceof Error) throw reply
    return {
      ok: reply.status >= 200 && reply.status < 300,
      status: reply.status,
      json: async () => reply.body ?? {},
      blob: async () => new Blob(),
      headers: new Headers(),
    } as unknown as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

let redirect: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  localStorage.clear()
  window.history.replaceState(null, '', '/progress?range=90')
  // jsdom does not implement navigation, so the redirect is observed here.
  redirect = vi.spyOn(session, 'redirectToLogin').mockImplementation(() => {})
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('a rejected token', () => {
  it('clears the stored token', async () => {
    saveToken('stale')
    mockFetch({ status: 401, body: { detail: 'Invalid token' } })
    await expect(request('/api/stats/home')).rejects.toThrow()
    expect(getToken()).toBeNull()
  })

  it('sends the user to the login page, remembering where they were', async () => {
    saveToken('stale')
    mockFetch({ status: 401, body: { detail: 'Invalid token' } })
    await expect(request('/api/stats/home')).rejects.toThrow()
    expect(redirect).toHaveBeenCalledOnce()
    expect(redirect).toHaveBeenCalledWith(
      `/login?expired=1&next=${encodeURIComponent('/progress?range=90')}`,
    )
  })

  it('is handled for the data export, which bypasses request()', async () => {
    saveToken('stale')
    mockFetch({ status: 401, body: { detail: 'Invalid token' } })
    await expect(exportData()).rejects.toThrow()
    expect(getToken()).toBeNull()
    expect(redirect).toHaveBeenCalledOnce()
  })
})

describe('failures that are not a rejected session', () => {
  it('a 401 on a request that sent no token does not redirect', async () => {
    mockFetch({ status: 401, body: { detail: 'Not authenticated' } })
    await expect(request('/api/stats/home')).rejects.toThrow('Not authenticated')
    expect(redirect).not.toHaveBeenCalled()
  })

  it('a server error keeps the session', async () => {
    saveToken('valid')
    mockFetch({ status: 500, body: { detail: 'boom' } })
    await expect(request('/api/stats/home')).rejects.toThrow('boom')
    expect(getToken()).toBe('valid')
    expect(redirect).not.toHaveBeenCalled()
  })

  it('a network failure keeps the session', async () => {
    saveToken('valid')
    mockFetch(new TypeError('Failed to fetch'))
    await expect(request('/api/stats/home')).rejects.toThrow('Failed to fetch')
    expect(getToken()).toBe('valid')
    expect(redirect).not.toHaveBeenCalled()
  })

  it('a 403 keeps the session', async () => {
    saveToken('valid')
    mockFetch({ status: 403, body: { detail: 'Admin only' } })
    await expect(request('/api/admin/users')).rejects.toThrow('Admin only')
    expect(getToken()).toBe('valid')
    expect(redirect).not.toHaveBeenCalled()
  })
})

describe('logging in with a stale token still in storage', () => {
  // The state a user is in when they reach /login after a rejected session,
  // or visit it directly as the workaround for this bug.

  it('does not send the stale token with the credentials', async () => {
    saveToken('stale')
    const fetchMock = mockFetch({ status: 200, body: { access_token: 'fresh', token_type: 'bearer' } })
    await login('dave', 'pw')
    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Record<string, string>
    expect(headers.Authorization).toBeUndefined()
    expect(getToken()).toBe('fresh')
  })

  it('reports a wrong password on the form instead of redirecting', async () => {
    saveToken('stale')
    mockFetch({ status: 401, body: { detail: 'Incorrect username or password' } })
    await expect(login('dave', 'wrong')).rejects.toThrow('Incorrect username or password')
    expect(redirect).not.toHaveBeenCalled()
  })
})
