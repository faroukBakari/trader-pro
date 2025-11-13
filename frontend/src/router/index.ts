import { ApiAdapter } from '@/plugins/apiAdapter'
import { createRouter, createWebHistory } from 'vue-router'

const apiAdapter = ApiAdapter.getInstance()

interface CachedAuthCheck {
  isValid: boolean
  timestamp: number
}

let cachedAuthCheck: CachedAuthCheck | null = null
const CACHE_TTL = 30000 // 30 seconds

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/chart',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: {
        requiresAuth: false,
      },
    },
    {
      path: '/chart',
      name: 'trader-chart',
      component: () => import('../views/TraderChartView.vue'),
      meta: {
        requiresAuth: true,
      },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../views/NotFoundView.vue'),
    },
  ],
})

async function checkAuthStatus(): Promise<boolean> {
  const now = Date.now()

  if (cachedAuthCheck && cachedAuthCheck.isValid && now - cachedAuthCheck.timestamp < CACHE_TTL) {
    return cachedAuthCheck.isValid
  }

  try {
    const result = await apiAdapter.introspectToken()
    const isValid = result.data.status === 'valid'

    cachedAuthCheck = { isValid, timestamp: now }

    return isValid
  } catch {
    cachedAuthCheck = { isValid: false, timestamp: now }
    return false
  }
}

router.beforeEach(async (to, from, next) => {
  const requiresAuth = to.meta.requiresAuth === true
  const isAuthenticated = await checkAuthStatus()

  if (requiresAuth && !isAuthenticated) {
    next({
      name: 'login',
      query: { redirect: to.fullPath },
    })
    return
  }

  if (to.name === 'login' && isAuthenticated) {
    next({ name: 'trader-chart' })
    return
  }

  next()
})

export default router
