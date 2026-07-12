import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error): void {
    console.error('ErrorBoundary caught an unhandled error:', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 p-8 text-center">
          <h2 className="text-xl font-bold text-[var(--color-text)]">Something went wrong</h2>
          <p className="text-[14px] text-[var(--color-muted)]">
            This page ran into an unexpected error.
          </p>
          <a href="/" className="text-[var(--color-accent)] font-semibold text-[14px] underline">
            Go home
          </a>
        </div>
      )
    }
    return this.props.children
  }
}
