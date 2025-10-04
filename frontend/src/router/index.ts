import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/api-status',
    },
    {
      path: '/api-status',
      name: 'api-status',
      component: () => import('../views/ApiStatusView.vue'),
    },
  ],
})

export default router
