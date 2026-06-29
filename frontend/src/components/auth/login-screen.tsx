import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from '@tanstack/react-router'
import ubsLogo from '@/assets/UBS_Logo.svg'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { LoginError } from '@/lib/auth-client'
import { useAuth } from '@/lib/use-auth'
import type { UserRole } from '@/lib/auth-contract'

type AppHome = '/jd-studio' | '/hr-portal'
type LoginPath = '/login' | '/hr-login'

interface LoginScreenProps {
  /** Role this screen signs in as; sent as expected_role and enforced by the backend. */
  role: UserRole
  /** Portal name shown in the heading, e.g. "Manager Portal". */
  portalLabel: string
  /** Where to land on success. */
  home: AppHome
  /** Link to the other portal's login. */
  crossLink: { to: LoginPath; label: string; blurb: string }
}

/** The shared login card behind both the manager and HR screens. */
export function LoginScreen({
  role,
  portalLabel,
  home,
  crossLink,
}: Readonly<LoginScreenProps>) {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      await login({ email, password, expectedRole: role })
      await navigate({ to: home })
    } catch (cause) {
      setError(
        cause instanceof LoginError && cause.status === 401
          ? 'Wrong credentials.'
          : 'Something went wrong. Please try again.',
      )
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <header className="flex h-16 items-center gap-3.5 border-b border-border bg-surface px-6">
        <img src={ubsLogo} alt="UBS" className="h-6 w-auto" />
        <span className="h-5 w-px bg-border" aria-hidden="true" />
        <span className="font-sans text-label text-ink-muted">
          Pattern Mirror
        </span>
      </header>

      <main className="flex flex-1 flex-col items-center justify-center px-6">
        <div className="w-full max-w-md">
          <div className="rounded-card border border-border bg-surface px-10 py-9 shadow-ring-card">
            <h1 className="text-center font-serif text-title text-ink">
              Greetings
            </h1>
            <p className="mt-2 text-center font-sans text-body-sm text-ink-muted">
              Sign in to the{' '}
              <span className="font-semibold text-red-primary">
                {portalLabel}
              </span>
            </p>

            <form className="mt-7 flex flex-col gap-4" onSubmit={handleSubmit}>
              <label className="flex flex-col gap-1.5">
                <span className="font-sans text-label text-ink-muted">
                  Username
                </span>
                <Input
                  type="text"
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="font-sans text-label text-ink-muted">
                  Password
                </span>
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
              </label>

              {error && (
                <p
                  role="alert"
                  className="font-sans text-meta text-red-primary"
                >
                  {error}
                </p>
              )}

              <Button
                type="submit"
                size="lg"
                className="mt-1 w-full"
                disabled={pending}
              >
                {pending ? 'Signing in…' : 'Log in'}
              </Button>
            </form>
          </div>

          <p className="mt-4 text-center font-sans text-meta text-ink-muted">
            <Link to={crossLink.to} className="font-semibold text-red-primary">
              {crossLink.label}
            </Link>{' '}
            — {crossLink.blurb}
          </p>
          <p className="mt-6 text-center font-sans text-micro text-ink-faint">
            The Pattern Mirror · UBS Tomorrow's Talent Programme 2026
          </p>
        </div>
      </main>
    </div>
  )
}
