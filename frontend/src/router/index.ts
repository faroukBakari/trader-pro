import { WebSocketBase } from '@/plugins/wsClientBase'
import { useAuthService } from '@/services/authService'
import { createRouter, createWebHistory } from 'vue-router'

const authService = useAuthService()
let authMonitorTimeout: NodeJS.Timeout | null = null

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


async function watchAuthStatus() {
  if (router.currentRoute.value.meta.requiresAuth) {
    const isValid = await authService.checkAuthStatus()

    if (!isValid) {
      console.log('Token expired or invalid - disconnecting WebSockets and redirecting to login')

      WebSocketBase.logout()

      router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })

    } else {
      authMonitorTimeout = setTimeout(watchAuthStatus, 10 * 1000) // Check again in 10 seconds
    }
  }
}

router.beforeEach(async (to, _, next) => {
  const isAuthenticated = await authService.checkAuthStatus()

  if (authMonitorTimeout) {
    clearTimeout(authMonitorTimeout)
    authMonitorTimeout = null
  }

  if (to.name === 'login' && isAuthenticated) {
    return next({ name: 'trader-chart' })
  }

  if (to.meta.requiresAuth) {
    if (isAuthenticated) {
      authMonitorTimeout = setTimeout(watchAuthStatus, 10 * 1000)
      return next()
    }

    return to.name != 'login'
      ? next({
        name: 'login',
        query: { redirect: to.fullPath },
      })
      : next()
  }

  return next()
})

export default router
