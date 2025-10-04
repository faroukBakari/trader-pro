import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ApiStatus from '../ApiStatus.vue'
import * as apiService from '@/services/apiService'
import type { HealthResponse, APIMetadata } from '@/services/apiService'

// Mock the API service
vi.mock('@/services/apiService', () => ({
  apiService: {
    getHealth: vi.fn(),
    getVersions: vi.fn(),
  },
}))

describe('ApiStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the component with title', () => {
    // Mock successful API responses
    vi.mocked(apiService.apiService.getHealth).mockResolvedValue({
      status: 'ok',
      message: 'Trading API is running',
      timestamp: '2025-01-01T00:00:00Z',
      api_version: 'v1',
      version_info: {
        version: 'v1',
        release_date: '2025-01-01',
        status: 'stable',
        deprecation_notice: null,
      },
    })

    vi.mocked(apiService.apiService.getVersions).mockResolvedValue({
      current_version: 'v1',
      available_versions: [
        {
          version: 'v1',
          status: 'stable',
          release_date: '2025-01-01',
          deprecation_notice: null,
          sunset_date: null,
        },
      ],
      documentation_url: 'https://api.example.com/docs',
      support_contact: 'support@example.com',
    })

    const wrapper = mount(ApiStatus)
    expect(wrapper.text()).toContain('API Status')
    expect(wrapper.text()).toContain('Health Check')
    expect(wrapper.text()).toContain('API Versions')
  })

  it('shows loading state initially', async () => {
    // Mock pending promises that never resolve
    const healthPromise = new Promise<HealthResponse>(() => {}) // Never resolves
    const versionsPromise = new Promise<APIMetadata>(() => {}) // Never resolves

    vi.mocked(apiService.apiService.getHealth).mockReturnValue(healthPromise)
    vi.mocked(apiService.apiService.getVersions).mockReturnValue(versionsPromise)

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
})
