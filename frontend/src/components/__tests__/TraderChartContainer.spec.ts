import { ihmController } from '@/services/ihmControllerService'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import TraderChartContainer from '../TraderChartContainer.vue'

// Mock the TradingView widget
vi.mock('@public/trading_terminal', () => ({
  widget: vi.fn().mockImplementation(() => ({
    onChartReady: vi.fn((callback) => {
      // Simulate chart ready after a short delay
      setTimeout(callback, 50)
    }),
    headerReady: vi.fn().mockResolvedValue(undefined),
    createButton: vi.fn().mockReturnValue({
      setAttribute: vi.fn(),
      classList: {
        add: vi.fn(),
      },
      addEventListener: vi.fn(),
      innerHTML: '',
    }),
    setDebugMode: vi.fn(),
    showNoticeDialog: vi.fn(),
    remove: vi.fn(),
    setSymbol: vi.fn((symbol, interval, callback) => {
      // Simulate async symbol change
      setTimeout(() => callback?.(), 10)
    }),
  })),
}))

// Mock DatafeedService
vi.mock('@/services/datafeedService', () => ({
  DatafeedService: vi.fn().mockImplementation(() => ({})),
}))

// Mock BrokerTerminalService
vi.mock('@/services/brokerTerminalService', () => ({
  BrokerTerminalService: vi.fn().mockImplementation(() => ({
    destroy: vi.fn().mockResolvedValue(undefined),
  })),
}))

describe('TraderChartContainer Tool Registration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should register displayStockChart tool when chart is ready', async () => {
    const registerSpy = vi.spyOn(ihmController, 'registerTool')

    const wrapper = mount(TraderChartContainer, {
      props: { enableTrading: false },
    })

    // Wait for chart ready callback to execute
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(registerSpy).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ name: 'displayStockChart' }),
      expect.any(Function),
    )

    wrapper.unmount()
  })

  it('should unregister tool on component unmount', async () => {
    const unregisterSpy = vi.spyOn(ihmController, 'unregisterTool')

    const wrapper = mount(TraderChartContainer, {
      props: { enableTrading: false },
    })

    // Wait for chart ready
    await new Promise((resolve) => setTimeout(resolve, 100))

    wrapper.unmount()

    expect(unregisterSpy).toHaveBeenCalledExactlyOnceWith('displayStockChart')
  })

  it('should include required parameters in tool schema', async () => {
    const registerSpy = vi.spyOn(ihmController, 'registerTool')

    const wrapper = mount(TraderChartContainer, {
      props: { enableTrading: false },
    })

    // Wait for chart ready
    await new Promise((resolve) => setTimeout(resolve, 100))

    expect(registerSpy).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        name: 'displayStockChart',
        description: expect.any(String),
        parameters: expect.objectContaining({
          type: 'object',
          properties: expect.objectContaining({
            symbol: expect.objectContaining({
              type: 'string',
              description: expect.any(String),
            }),
          }),
          required: expect.arrayContaining(['symbol']),
        }),
      }),
      expect.any(Function),
    )

    wrapper.unmount()
  })
})
