import { Component, type ErrorInfo, type ReactNode } from 'react'
import { ErrorState } from '@/ui'

interface State {
  failed: boolean
}

/** Catches a screen that crashes, or a chunk that fails to load after a new deploy. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Screen failed', error, info.componentStack)
  }

  render() {
    if (this.state.failed) {
      return (
        <ErrorState
          title="This screen could not load"
          description="Reload to get the latest version. If it keeps happening, tell us what you were doing."
          onRetry={() => window.location.reload()}
        />
      )
    }
    return this.props.children
  }
}
