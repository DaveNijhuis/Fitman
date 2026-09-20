import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ErrorBoundary from '../ErrorBoundary'

function Bomb(): never {
  throw new Error('test explosion')
}

function SafeChild() {
  return <div>all good</div>
}

describe('ErrorBoundary', () => {
  beforeEach(() => {
    // suppress React's console.error for expected thrown errors
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <SafeChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('all good')).toBeInTheDocument()
  })

  it('renders a fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )
    expect(screen.getByRole('heading', { level: 2 })).toBeInTheDocument()
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
  })

  it('fallback contains a link back to home', () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>
    )
    const link = screen.getByRole('link')
    expect(link).toHaveAttribute('href', '/')
  })

  it('multiple independent boundaries do not interfere', () => {
    render(
      <div>
        <ErrorBoundary>
          <Bomb />
        </ErrorBoundary>
        <ErrorBoundary>
          <SafeChild />
        </ErrorBoundary>
      </div>
    )
    expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    expect(screen.getByText('all good')).toBeInTheDocument()
  })
})
