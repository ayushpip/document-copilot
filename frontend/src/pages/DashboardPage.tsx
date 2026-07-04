import { useEffect, useState } from 'react'
import { LogOut, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'

type CurrentUserResponse = {
  user_id: string
  email: string | null
}

type ApiStatus =
  | { state: 'checking' }
  | { state: 'connected'; user: CurrentUserResponse }
  | { state: 'error'; message: string }

export function DashboardPage() {
  const { user, signOut } = useAuth()
  const [apiStatus, setApiStatus] = useState<ApiStatus>({ state: 'checking' })

  async function checkBackendSession(showChecking = true) {
    if (showChecking) {
      setApiStatus({ state: 'checking' })
    }

    try {
      const currentUser = await api.get<CurrentUserResponse>('/auth/me')
      setApiStatus({ state: 'connected', user: currentUser })
    } catch (error) {
      setApiStatus({
        state: 'error',
        message: error instanceof Error ? error.message : 'Unable to reach the authenticated API.',
      })
    }
  }

  useEffect(() => {
    let isMounted = true

    api
      .get<CurrentUserResponse>('/auth/me')
      .then((currentUser) => {
        if (isMounted) {
          setApiStatus({ state: 'connected', user: currentUser })
        }
      })
      .catch((error: unknown) => {
        if (isMounted) {
          setApiStatus({
            state: 'error',
            message: error instanceof Error ? error.message : 'Unable to reach the authenticated API.',
          })
        }
      })

    return () => {
      isMounted = false
    }
  }, [])

  return (
    <main className="min-h-svh bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
          <div className="text-left">
            <p className="text-sm font-semibold">Document Copilot</p>
            <p className="text-xs text-muted-foreground">{user?.email ?? 'Signed in analyst'}</p>
          </div>
          <Button variant="outline" onClick={() => void signOut()}>
            <LogOut />
            Sign out
          </Button>
        </div>
      </header>

      <section className="mx-auto grid max-w-6xl gap-6 px-6 py-8 text-left lg:grid-cols-[1fr_320px]">
        <div className="rounded-lg border border-border bg-card p-6">
          <p className="text-sm font-medium text-muted-foreground">Analyst workspace</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-normal text-foreground">Ask filings with citations</h1>
          <div className="mt-8 min-h-[240px] rounded-lg border border-dashed border-border bg-muted/40 p-6 text-sm text-muted-foreground">
            The chat surface comes next. Auth is now protecting this workspace, and the backend token check is available on the right.
          </div>
        </div>

        <aside className="rounded-lg border border-border bg-card p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Backend auth</h2>
              <p className="mt-1 text-sm text-muted-foreground">Checks whether your Supabase token reaches FastAPI.</p>
            </div>
            <Button variant="ghost" size="icon" onClick={() => void checkBackendSession()} aria-label="Refresh backend auth status">
              <RefreshCw />
            </Button>
          </div>

          <div className="mt-5 rounded-md border border-border bg-background p-4 text-sm">
            {apiStatus.state === 'checking' ? <p className="text-muted-foreground">Checking...</p> : null}
            {apiStatus.state === 'connected' ? (
              <div className="space-y-2">
                <p className="font-medium text-foreground">Connected</p>
                <p className="break-all text-muted-foreground">{apiStatus.user.email ?? apiStatus.user.user_id}</p>
              </div>
            ) : null}
            {apiStatus.state === 'error' ? (
              <div className="space-y-2">
                <p className="font-medium text-destructive">Not connected</p>
                <p className="text-muted-foreground">{apiStatus.message}</p>
              </div>
            ) : null}
          </div>
        </aside>
      </section>
    </main>
  )
}
