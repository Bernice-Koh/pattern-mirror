import {
  createRootRoute,
  createRoute,
  createRouter,
} from '@tanstack/react-router'
import { AppShell } from '@/components/app-shell'
import { RouteError } from '@/components/route-error'
import { JdStudio } from '@/pages/jd-studio'
import { FeedbackCheckpoint } from '@/pages/feedback-checkpoint'
import { PatternDashboard } from '@/pages/pattern-dashboard'
import { PromotionWriteup } from '@/pages/promotion-writeup'
import { HrPortal } from '@/pages/hr-portal'
import { HrDictionaryReview } from '@/pages/hr-dictionary-review'
import { Login } from '@/pages/login'
import { HrLogin } from '@/pages/hr-login'
import {
  indexRedirect,
  redirectIfAuthenticated,
  requireRole,
} from '@/lib/auth-guards'

const rootRoute = createRootRoute()

/** Search for opening a specific document in its surface from My Documents (#69). */
interface DocSearch {
  doc?: string
}

function validateDocSearch(search: Record<string, unknown>): DocSearch {
  return { doc: typeof search.doc === 'string' ? search.doc : undefined }
}

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
  validateSearch: validateDocSearch,
  component: JdStudio,
})

const feedbackCheckpointRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/feedback-checkpoint',
  beforeLoad: requireRole('manager'),
  validateSearch: validateDocSearch,
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
  validateSearch: validateDocSearch,
  component: PromotionWriteup,
})

const hrPortalRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/hr-portal',
  beforeLoad: requireRole('hr'),
  component: HrPortal,
})

/** Search for opening a specific pending addition in the review modal from the HR Portal card. */
interface ReviewSearch {
  addition?: string
}

function validateReviewSearch(search: Record<string, unknown>): ReviewSearch {
  return {
    addition: typeof search.addition === 'string' ? search.addition : undefined,
  }
}

const hrDictionaryReviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: '/hr-portal/dictionary-review',
  beforeLoad: requireRole('hr'),
  validateSearch: validateReviewSearch,
  component: HrDictionaryReview,
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
    hrDictionaryReviewRoute,
  ]),
])

export const router = createRouter({
  routeTree,
  defaultErrorComponent: RouteError,
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
