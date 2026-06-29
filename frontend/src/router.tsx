import {
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { AppShell } from '@/components/app-shell'
import { JdStudio } from '@/pages/jd-studio'
import { FeedbackCheckpoint } from '@/pages/feedback-checkpoint'
import { PatternDashboard } from '@/pages/pattern-dashboard'
import { PromotionWriteup } from '@/pages/promotion-writeup'
import { HrPortal } from '@/pages/hr-portal'
import { Login } from '@/pages/login'
import { HrLogin } from '@/pages/hr-login'
import {
  indexRedirect,
  redirectIfAuthenticated,
  requireRole,
} from '@/lib/auth-guards'

const rootRoute = createRootRoute()

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: indexRedirect,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  beforeLoad: redirectIfAuthenticated,
  component: Login,
})

const hrLoginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/hr-login',
  beforeLoad: redirectIfAuthenticated,
  component: HrLogin,
})

// Authenticated surfaces render inside the app chrome; the role guards live on each leaf.
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'app',
  component: AppShell,
})

const jdStudioRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/jd-studio',
  beforeLoad: requireRole('manager'),
  component: JdStudio,
})

const feedbackCheckpointRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/feedback-checkpoint',
  beforeLoad: requireRole('manager'),
  component: FeedbackCheckpoint,
})

const patternDashboardRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/pattern-dashboard',
  beforeLoad: requireRole('manager'),
  component: PatternDashboard,
})

const promotionWriteupRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/promotion-writeup',
  beforeLoad: requireRole('manager'),
  component: PromotionWriteup,
})

const hrPortalRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/hr-portal',
  beforeLoad: requireRole('hr'),
  component: HrPortal,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  hrLoginRoute,
  appRoute.addChildren([
    jdStudioRoute,
    feedbackCheckpointRoute,
    patternDashboardRoute,
    promotionWriteupRoute,
    hrPortalRoute,
  ]),
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
