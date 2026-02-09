import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ApiStatus from '../ApiStatus.vue'

// Mock ApiService
vi.mock('@/services/apiService', () => {
  // Mock data must be defined inside the factory
  const mockModules = [
    {
      name: 'broker',
      displayName: 'Broker',
      docsUrl: '/api/v1/broker/docs',
      hasWebSocket: true,
    },
    {
      name: 'datafeed',
      displayName: 'Datafeed',
      docsUrl: '/api/v1/datafeed/docs',
      hasWebSocket: true,
    },
  ]

  const mockHealth = new Map([
    [
      'broker',
      {
        moduleName: 'broker',
        health: { status: 'ok', message: 'Service operational' },
        loading: false,
        error: null,
        responseTime: 45,
      },
    ],
    [
      'datafeed',
      {
        moduleName: 'datafeed',
        health: { status: 'ok', message: 'Service operational' },
        loading: false,
        error: null,
        responseTime: 32,
      },
    ],
  ])

  const MockApiService = vi.fn().mockImplementation(() => ({
    getAllModulesHealth: vi.fn().mockResolvedValue(mockHealth),
    getClientType: vi.fn().mockReturnValue('mock'),
  }))

  // Add static method to the mock constructor (bypassing type checking for test mock)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(MockApiService as any).getIntegratedModules = vi.fn().mockReturnValue(mockModules)

  return {
    ApiService: MockApiService,
  }
})

describe('ApiStatus - Collapsed Pill', () => {
  it('renders pill in collapsed state by default', () => {
    const wrapper = mount(ApiStatus)
    expect(wrapper.find('.status-pill').exists()).toBe(true)
    expect(wrapper.find('.status-panel').exists()).toBe(false)
  })

  it('pill contains status dot and API label', () => {
    const wrapper = mount(ApiStatus)
    const pill = wrapper.find('.status-pill')
    expect(pill.find('.status-dot').exists()).toBe(true)
    expect(pill.find('.pill-label').text()).toBe('API')
  })

  it('pill has aria-label for accessibility', () => {
    const wrapper = mount(ApiStatus)
    const pill = wrapper.find('.status-pill')
    expect(pill.attributes('aria-label')).toBe('API Status')
  })
})

describe('ApiStatus - Panel Expand/Collapse', () => {
  it('expands panel on pill click', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(true)
    expect(wrapper.find('.status-pill').exists()).toBe(false)
  })

  it('collapses panel on close button click', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(true)

    await wrapper.find('.close-btn').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(false)
    expect(wrapper.find('.status-pill').exists()).toBe(true)
  })

  it('collapses panel on Escape key', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(true)

    await wrapper.find('.status-panel').trigger('keydown.esc')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(false)
    expect(wrapper.find('.status-pill').exists()).toBe(true)
  })

  it('starts auto-collapse timer on mouseleave', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ApiStatus)

    // Expand panel
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.find('.status-panel').exists()).toBe(true)

    // Trigger mouseleave
    await wrapper.find('.api-status-overlay').trigger('mouseleave')

    // Panel should still be open
    expect(wrapper.find('.status-panel').exists()).toBe(true)

    // Fast-forward 3 seconds
    vi.advanceTimersByTime(3000)
    await wrapper.vm.$nextTick()

    // Panel should now be collapsed
    expect(wrapper.find('.status-panel').exists()).toBe(false)
    expect(wrapper.find('.status-pill').exists()).toBe(true)

    vi.useRealTimers()
  })

  it('cancels auto-collapse timer on mouseenter', async () => {
    vi.useFakeTimers()
    const wrapper = mount(ApiStatus)

    // Expand panel
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    // Start collapse timer
    await wrapper.find('.api-status-overlay').trigger('mouseleave')

    // Fast-forward 1.5 seconds (half the timer)
    vi.advanceTimersByTime(1500)

    // Re-enter before timer expires
    await wrapper.find('.api-status-overlay').trigger('mouseenter')

    // Fast-forward past original timer
    vi.advanceTimersByTime(2000)
    await wrapper.vm.$nextTick()

    // Panel should still be open (timer was cancelled)
    expect(wrapper.find('.status-panel').exists()).toBe(true)

    vi.useRealTimers()
  })
})

describe('ApiStatus - Panel Content', () => {
  it('shows header with API Status title', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const header = wrapper.find('.panel-header')
    expect(header.exists()).toBe(true)
    expect(header.text()).toContain('API Status')
  })

  it('shows client type badge', async () => {
    const wrapper = mount(ApiStatus)
    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const badge = wrapper.find('.client-badge')
    expect(badge.exists()).toBe(true)
    expect(badge.text()).toBe('mock')
  })

  it('shows module rows after data loads', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const rows = wrapper.findAll('.module-row')
    expect(rows.length).toBe(2)
  })

  it('displays module names in rows', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const text = wrapper.text()
    expect(text).toContain('Broker')
    expect(text).toContain('Datafeed')
  })

  it('shows health status dots in module rows', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const rows = wrapper.findAll('.module-row')
    rows.forEach((row) => {
      expect(row.find('.status-dot').exists()).toBe(true)
    })
  })

  it('has a refresh button in the panel', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const refreshBtn = wrapper.find('.refresh-btn')
    expect(refreshBtn.exists()).toBe(true)
    expect(refreshBtn.text()).toContain('Refresh')
  })

  it('refresh button triggers data reload', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const refreshBtn = wrapper.find('.refresh-btn')
    await refreshBtn.trigger('click')
    await flushPromises()
    await wrapper.vm.$nextTick()

    // Should still show rows after refresh
    const rows = wrapper.findAll('.module-row')
    expect(rows.length).toBe(2)
  })

  it('displays module doc links', async () => {
    const wrapper = mount(ApiStatus)
    await flushPromises()
    await wrapper.vm.$nextTick()

    await wrapper.find('.status-pill').trigger('click')
    await wrapper.vm.$nextTick()

    const links = wrapper.findAll('.module-link')
    expect(links.length).toBe(2)
  })
})
