import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import NotFoundView from '@/views/NotFoundView.vue'

// Create a simple mock router
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div>Home</div>' } },
    { path: '/:pathMatch(.*)*', component: NotFoundView },
  ],
})

describe('NotFoundView', () => {
  it('renders 404 message and content', () => {
    const wrapper = mount(NotFoundView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.text()).toContain('404')
    expect(wrapper.text()).toContain('Page Not Found')
    expect(wrapper.text()).toContain("The page you are looking for doesn't exist or has been moved")
    expect(wrapper.text()).toContain('Go to API Status')
    expect(wrapper.text()).toContain('Go Back')
  })

  it('has proper CSS classes for styling', () => {
    const wrapper = mount(NotFoundView, {
      global: {
        plugins: [router],
      },
    })

    expect(wrapper.find('.not-found').exists()).toBe(true)
    expect(wrapper.find('.not-found-content').exists()).toBe(true)
    expect(wrapper.find('.actions').exists()).toBe(true)
  })

  it('contains navigation elements', () => {
    const wrapper = mount(NotFoundView, {
      global: {
        plugins: [router],
      },
    })

    const actionButtons = wrapper.find('.actions')
    expect(actionButtons.exists()).toBe(true)

    // Check that there are action elements (router-link and button)
    expect(actionButtons.html()).toContain('Go to API Status')
    expect(actionButtons.html()).toContain('Go Back')
  })
})
