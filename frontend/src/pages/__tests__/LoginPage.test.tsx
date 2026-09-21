import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import LoginPage from '../LoginPage'
import * as auth from '../../api/auth'

/**
 * After a rejected session the user lands on /login?expired=1&next=<page>
 * (#317). The page must say why they are there and take them back afterwards —
 * but only to a path on this site, or the link becomes an open redirect.
 */

function Where() {
  const location = useLocation()
  return <div data-testid="where">{location.pathname + location.search}</div>
}

function renderAt(url: string) {
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )
}

async function signIn() {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'dave' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pw' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
  return screen.findByTestId('where')
}

beforeEach(() => {
  vi.spyOn(auth, 'login').mockResolvedValue(undefined)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('LoginPage after an expired session', () => {
  it('explains why the user was sent here', () => {
    renderAt('/login?expired=1&next=%2Fprogress')
    expect(screen.getByTestId('session-expired')).toHaveTextContent(/session.*expired/i)
  })

  it('shows no expiry notice on an ordinary visit', () => {
    renderAt('/login')
    expect(screen.queryByTestId('session-expired')).toBeNull()
  })

  it('returns the user to the page they were on', async () => {
    renderAt(`/login?expired=1&next=${encodeURIComponent('/progress?range=90')}`)
    expect(await signIn()).toHaveTextContent('/progress?range=90')
  })

  it('goes home when there is no page to return to', async () => {
    renderAt('/login')
    expect(await signIn()).toHaveTextContent(/^\/$/)
  })

  it.each([
    ['another site', 'https://evil.example/'],
    ['a protocol-relative URL', '//evil.example/'],
    ['a backslash URL browsers treat as protocol-relative', '/\\evil.example/'],
    ['a relative path', 'progress'],
    ['the login page itself', '/login'],
  ])('ignores %s as a destination', async (_label, next) => {
    renderAt(`/login?next=${encodeURIComponent(next)}`)
    expect(await signIn()).toHaveTextContent(/^\/$/)
  })

  it('still shows a wrong-password error', async () => {
    vi.mocked(auth.login).mockRejectedValue(new Error('Incorrect username or password'))
    renderAt('/login?expired=1&next=%2Fprogress')
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'dave' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'bad' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() =>
      expect(screen.getByTestId('login-error')).toHaveTextContent('Incorrect username or password'),
    )
  })
})
