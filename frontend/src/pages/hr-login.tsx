import { LoginScreen } from '@/components/auth/login-screen'

/** HR Portal login. */
export function HrLogin() {
  return (
    <LoginScreen
      role="hr"
      portalLabel="HR Portal"
      home="/hr-portal"
      crossLink={{
        to: '/login',
        label: 'Access Manager Portal',
        blurb: 'For manager access, please use the manager login.',
      }}
    />
  )
}
