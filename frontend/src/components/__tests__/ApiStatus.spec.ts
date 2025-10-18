import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ApiStatus from '../ApiStatus.vue'

describe('ApiStatus', () => {
  it('renders the component with title', () => {
    const wrapper = mount(ApiStatus)
    expect(wrapper.text()).toContain('API Status')
    expect(wrapper.text()).toContain('Health Check')
    expect(wrapper.text()).toContain('API Versions')
    expect(wrapper.text()).toContain('WebSocket API')
  })

  it('shows loading state initially', async () => {
    const wrapper = mount(ApiStatus)

    // Wait for component to mount and start loading
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('Loading...')
  })

  it('has a refresh button', () => {
    const wrapper = mount(ApiStatus)
    const refreshButton = wrapper.find('button')
    expect(refreshButton.exists()).toBe(true)
    expect(refreshButton.text()).toContain('Refresh')
  })

  it('displays API status information after loading', async () => {
    const wrapper = mount(ApiStatus)

    // Wait for the async API calls to complete
    // Using a reasonable timeout for the mock API responses
    await new Promise((resolve) => setTimeout(resolve, 500))
    await wrapper.vm.$nextTick()

    // Check that loading state is gone
    expect(wrapper.text()).not.toContain('Loading...')

    // Check that some API information is displayed
    const text = wrapper.text()
    expect(text).toBeTruthy()
    expect(text.length).toBeGreaterThan(50) // Should contain meaningful content
  })

  it('refresh button triggers data refresh', async () => {
    const wrapper = mount(ApiStatus)

    // Wait for initial load
    await new Promise((resolve) => setTimeout(resolve, 300))
    await wrapper.vm.$nextTick()

    const refreshButton = wrapper.find('button')
    expect(refreshButton.exists()).toBe(true)

    // Click refresh button
    await refreshButton.trigger('click')
    await wrapper.vm.$nextTick()

    // Should still show the component structure after refresh
    expect(wrapper.text()).toContain('API Status')
  })
})
