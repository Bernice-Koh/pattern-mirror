import { LoginScreen } from '@/components/auth/login-screen'

/** Manager Portal login. */
export function Login() {
  return (
    <LoginScreen
      role="manager"
      portalLabel="Manager Portal"
      home="/jd-studio"
      crossLink={{
        to: '/hr-login',
        label: 'Access HR Portal',
        blurb: 'For HR access, please use the dedicated HR login.',
      }}
    />
  )
}
