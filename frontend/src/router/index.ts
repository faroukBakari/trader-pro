import { useAuthStore } from '@/stores/authStore'
import { createRouter, createWebHistory } from 'vue-router'

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

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  const requiresAuth = to.meta.requiresAuth === true

  if (requiresAuth) {
    if (!authStore.isAuthenticated) {
      await authStore.initAuth()
    }

    if (!authStore.isAuthenticated) {
      next({
        name: 'login',
        query: { redirect: to.fullPath },
      })
      return
    }
  }

  if (to.name === 'login' && authStore.isAuthenticated) {
    next({ name: 'trader-chart' })
    return
  }

  next()
})

export default router
