import type { UserRole } from '@/lib/auth-contract'

/** The five manager/HR surfaces, in display order, each tagged with the role that owns it. Single
 *  source for the top-bar label and the surface nav; the nav renders only the current role's own
 *  surfaces (managers never see HR Portal, HR never sees the manager surfaces). */
export const SURFACES: readonly {
  path: string
  label: string
  role: UserRole
}[] = [
  { path: '/jd-studio', label: 'JD Studio', role: 'manager' },
  {
    path: '/feedback-checkpoint',
    label: 'Feedback Checkpoint',
    role: 'manager',
  },
  { path: '/pattern-dashboard', label: 'Pattern Dashboard', role: 'manager' },
  { path: '/promotion-writeup', label: 'Promotion Writeup', role: 'manager' },
  { path: '/hr-portal', label: 'HR Portal', role: 'hr' },
]
