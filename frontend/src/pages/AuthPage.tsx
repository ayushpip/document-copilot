import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/auth-context'
import { supabase } from '@/lib/supabase'

type AuthMode = 'login' | 'signup'

type LocationState = {
  from?: {
    pathname?: string
  }
}

export function AuthPage({ mode }: { mode: AuthMode }) {
  const { status } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const isSignup = mode === 'signup'
  const locationState = location.state as LocationState | null
  const nextPath = locationState?.from?.pathname ?? '/'

  if (status === 'authenticated') {
    return <Navigate to={nextPath} replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    setIsSubmitting(true)

    const credentials = {
      email: email.trim(),
      password,
    }

    const result = isSignup
      ? await supabase.auth.signUp({
          ...credentials,
          options: { emailRedirectTo: window.location.origin },
        })
      : await supabase.auth.signInWithPassword(credentials)

    setIsSubmitting(false)

    if (result.error) {
      setError(result.error.message)
      return
    }

    if (isSignup && !result.data.session) {
      setMessage('Check your email to confirm your account, then sign in.')
      return
    }

    navigate(nextPath, { replace: true })
  }

  return (
    <main className="min-h-svh bg-background text-foreground">
      <div className="mx-auto grid min-h-svh w-full max-w-6xl grid-cols-1 lg:grid-cols-[1fr_420px]">
        <section className="flex min-h-[320px] flex-col justify-between border-b border-border px-6 py-8 text-left lg:border-r lg:border-b-0 lg:px-10">
          <Link to="/" className="text-sm font-semibold tracking-normal text-foreground">
            Document Copilot
          </Link>
          <div className="max-w-xl py-12">
            <p className="text-sm font-medium text-muted-foreground">Driftwood Capital</p>
            <h1 className="mt-4 max-w-[12ch] text-5xl font-semibold leading-none tracking-normal text-foreground lg:text-6xl">
              Source-backed research intake
            </h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-muted-foreground">
              Sign in to query SEC filings, inspect cited passages, and keep analyst sessions tied to your account.
            </p>
          </div>
          <p className="text-sm text-muted-foreground">Email auth only. No SSO, no public access.</p>
        </section>

        <section className="flex items-center px-6 py-10 lg:px-10">
          <div className="w-full text-left">
            <div className="mb-8">
              <h2 className="text-2xl font-semibold text-foreground">{isSignup ? 'Create account' : 'Sign in'}</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {isSignup ? 'Use your Driftwood email to start a new account.' : 'Use your analyst account to continue.'}
              </p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              <label className="block text-sm font-medium text-foreground">
                Email
                <input
                  className="mt-2 h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
                  type="email"
                  value={email}
                  autoComplete="email"
                  required
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>

              <label className="block text-sm font-medium text-foreground">
                Password
                <input
                  className="mt-2 h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none transition focus:border-ring focus:ring-2 focus:ring-ring/30"
                  type="password"
                  value={password}
                  autoComplete={isSignup ? 'new-password' : 'current-password'}
                  minLength={6}
                  required
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>

              {error ? <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p> : null}
              {message ? <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm text-muted-foreground">{message}</p> : null}

              <Button className="h-10 w-full" type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="animate-spin" /> : null}
                {isSignup ? 'Create account' : 'Sign in'}
              </Button>
            </form>

            <p className="mt-6 text-center text-sm text-muted-foreground">
              {isSignup ? 'Already have an account?' : 'Need an account?'}{' '}
              <Link className="font-medium text-foreground underline-offset-4 hover:underline" to={isSignup ? '/login' : '/signup'}>
                {isSignup ? 'Sign in' : 'Create one'}
              </Link>
            </p>
          </div>
        </section>
      </div>
    </main>
  )
}
