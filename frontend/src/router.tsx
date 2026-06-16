import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'
import { AppShell } from '@/components/app-shell'
import { JdStudio } from '@/pages/jd-studio'
import { FeedbackCheckpoint } from '@/pages/feedback-checkpoint'
import { PatternDashboard } from '@/pages/pattern-dashboard'
import { PromotionWriteup } from '@/pages/promotion-writeup'
import { HrPortal } from '@/pages/hr-portal'

const rootRoute = createRootRoute({ component: AppShell })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/jd-studio' })
  },
})

const jdStudioRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/jd-studio',
  component: JdStudio,
})

const feedbackCheckpointRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/feedback-checkpoint',
  component: FeedbackCheckpoint,
})

const patternDashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/pattern-dashboard',
  component: PatternDashboard,
})

const promotionWriteupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/promotion-writeup',
  component: PromotionWriteup,
})

const hrPortalRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/hr-portal',
  component: HrPortal,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  jdStudioRoute,
  feedbackCheckpointRoute,
  patternDashboardRoute,
  promotionWriteupRoute,
  hrPortalRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
