<template>
  <div class="trader-chart-container">
    <h3>Trading Chart</h3>
    <div class="chart-wrapper">
      <div class="TVChartContainer" ref="chartContainer" />
    </div>
  </div>
</template>

<script setup lang="ts">
// other charting library sources : https://github.com/search?q=charting_library%2Fbundles%2Ffloating-toolbars.&type=code
import { onMounted, ref, onUnmounted } from 'vue'
import { DatafeedService } from '@/services/datafeedService'
import { BrokerTerminalService } from '@/services/brokerTerminalService'
import { ihmController } from '@/services/ihmControllerService'
import type { ToolSchema } from '@/types/ihmController'
import { widget } from '@public/trading_terminal'
import type {
  Brackets,
  IChartingLibraryWidget,
  IndividualPosition,
  LanguageCode,
  Order,
  OrderTicketFocusControl,
  Position,
  ResolutionString,
  TradingTerminalWidgetOptions,
  IBrokerConnectionAdapterHost,
} from '@public/trading_terminal'
import { ParentType } from '@public/trading_terminal'

const filterEmptyFields = (obj: object) => {
  return Object.fromEntries(Object.entries(obj).filter(([_, v]) => v != null))
}

function getLanguageFromURL() {
  const regex = new RegExp('[\\?&]lang=([^&#]*)')
  const results = regex.exec(window.location.search)
  return results === null
    ? null
    : (decodeURIComponent(results[1].replace(/\+/g, ' ')) as LanguageCode)
}

const props = defineProps({
  symbol: {
    default: 'NASDAQ:GOOGL',
    type: String,
  },
  interval: {
    default: '5',
    type: String,
  },
  // datafeedUrl: {
  //   default: 'https://demo_feed.trader-pro.com',
  //   type: String,
  // },
  libraryPath: {
    default: '/trading_terminal/',
    type: String,
  },
  // chartsStorageUrl: {
  //   default: 'https://saveload.trader-pro.com',
  //   type: String,
  // },
  // chartsStorageApiVersion: {
  //   default: '1.1',
  //   type: String,
  // },
  // clientId: {
  //   default: 'trader-pro.com',
  //   type: String,
  // },
  // userId: {
  //   default: 'public_user_id',
  //   type: String,
  // },
  fullscreen: {
    default: false,
    type: Boolean,
  },
  autosize: {
    default: true,
    type: Boolean,
  },
  studiesOverrides: {
    type: Object,
  },
  enableTrading: {
    default: true,
    type: Boolean,
  },
})

const chartContainer = ref<HTMLDivElement>()
let chartWidget: IChartingLibraryWidget | null = null
let brokerService: BrokerTerminalService | null = null

// Tool schema definition for IHM Controller
const displayStockChartSchema: ToolSchema = {
  name: 'displayStockChart',
  description: 'Display stock chart. Use for requests like "show AAPL chart" or "plot TSLA".',
  parameters: {
    type: 'object',
    properties: {
      symbol: {
        type: 'string',
        description: 'Stock ticker symbol (e.g., "AAPL", "TSLA")',
        pattern: '^[A-Z]{1,5}$',
      },
      timeframe: {
        type: 'string',
        description: 'Chart interval (e.g., "1D", "1W")',
        enum: ['1', '5', '15', '60', '1D', '1W', '1M'],
        default: '1D',
      },
    },
    required: ['symbol'],
  },
}

// Handler implementation for chart display tool
const displayStockChartHandler = async (params: { symbol: string; timeframe?: string }) => {
  if (!chartWidget) {
    throw new Error('Chart not ready')
  }

  await new Promise<void>((resolve) => {
    chartWidget!.setSymbol(params.symbol, (params.timeframe || '1D') as ResolutionString, () => {
      console.log(`[Chart] Switched to ${params.symbol} ${params.timeframe}`)
      resolve()
    })
  })
}

// Add chartWidget to global context for external access
declare global {
  interface Window {
    tradingViewChart?: IChartingLibraryWidget | null
  }
}

onMounted(() => {
  if (!chartContainer.value) {
    console.error('Chart container element not found')
    return
  }

  try {
    const datafeed = new DatafeedService()
    const widgetOptions: TradingTerminalWidgetOptions = {
      load_last_chart: true,
      symbol: props.symbol,
      datafeed,
      interval: props.interval as ResolutionString,
      container: chartContainer.value,
      library_path: props.libraryPath,

      locale: getLanguageFromURL() || 'en',
      theme: 'dark',
      enabled_features: ['pre_post_market_sessions'], // Extended sessions support
      disabled_features: ['study_templates', 'adaptive_logo'], // , 'use_localstorage_for_settings'

      // System color scheme overrides
      // need to clear site data on the browser to see the effect after changing these values
      overrides: {
        'paneProperties.backgroundGradientStartColor': '#131722',
        'paneProperties.backgroundGradientEndColor': '#131722',
        // 'paneProperties.background': '#181818',
        // 'paneProperties.backgroundType': 'solid',
        // 'paneProperties.vertGridProperties.color': '#282828',
        // 'paneProperties.horzGridProperties.color': '#282828',
        // 'paneProperties.crossHairProperties.color': 'rgba(84, 84, 84, 0.65)',
        // 'scalesProperties.backgroundColor': '#222222',
        // 'scalesProperties.lineColor': 'rgba(84, 84, 84, 0.48)',
        // 'scalesProperties.textColor': 'rgba(235, 235, 235, 0.64)',
      },
      // enabled_features: ['study_templates'], // Removed since we're disabling study_templates
      // charts_storage_url: props.chartsStorageUrl,
      // charts_storage_api_version: props.chartsStorageApiVersion as AvailableSaveloadVersions,
      // client_id: props.clientId,
      // user_id: props.userId,
      fullscreen: props.fullscreen,
      autosize: props.autosize,
      studies_overrides: props.studiesOverrides,

      debug: false,
      // debug_broker: 'all', // BrokerDebugMode.All,

      // Trading functionality
      ...(props.enableTrading && {
        broker_factory: (host: IBrokerConnectionAdapterHost) => {
          brokerService = new BrokerTerminalService(host, datafeed)
          return brokerService
        },
        broker_config: {
          configFlags: {
            supportClosePosition: true,
            supportNativeReversePosition: true,
            supportPLUpdate: true,
            supportExecutions: true,
            supportPositions: true,
            showQuantityInsteadOfAmount: false,
            supportLevel2Data: false,
            supportOrdersHistory: false,
            supportModifyOrderPreview: true,
            supportMargin: true,
            supportPositionBrackets: true,
            supportOrderBrackets: true,
            supportModifyOrderPrice: true,
            supportModifyBrackets: true,
            supportLimitOrders: true,
            supportStopOrders: true,
            supportStopLimitOrders: true,
            supportMarketBrackets: true,
            supportModifyDuration: true,
            supportModifyTrailingStop: true,
            supportPlaceOrderPreview: true,
            supportLeverage: true,
            supportLeverageButton: true,
          },
          // Custom UI hook to fix TradingView's position brackets preset bug
          // When user clicks edit from Account Manager, brackets are empty - we fetch them from orders
          customUI: {
            showPositionDialog: async (
              position: Position | IndividualPosition,
              newBrackets: Brackets,
              focus?: OrderTicketFocusControl,
            ): Promise<boolean> => {
              // If brackets are empty, fetch bracket orders for this position
              let existingBrackets = {}
              try {
                const orders: Order[] = await brokerService!.orders()
                const bracketOrders = orders.filter(
                  (o) =>
                    'parentId' in o &&
                    o.parentId === position.id &&
                    o.parentType === ParentType.Position,
                )
                // Find stop loss (has stopPrice) and take profit (has limitPrice)
                const stopLossOrder = bracketOrders.find((o) => o.stopPrice !== undefined)
                const takeProfitOrder = bracketOrders.find(
                  (o) => o.limitPrice !== undefined && o.stopPrice === undefined,
                )

                existingBrackets = {
                  ...(stopLossOrder?.stopPrice && { stopLoss: stopLossOrder?.stopPrice }),
                  ...(takeProfitOrder?.limitPrice && { takeProfit: takeProfitOrder?.limitPrice }),
                }
                console.log(
                  `[customUI.showPositionDialog] Enriched brackets for position ${position.id}:`,
                  existingBrackets,
                )
              } catch (e) {
                console.warn(`[customUI.showPositionDialog] Failed to fetch bracket orders:`, e)
              }

              const brackets = { ...existingBrackets, ...filterEmptyFields(newBrackets) } // Merge existing brackets

              return brokerService!.showPositionBracketsDialog(position, brackets, focus)
            },
          },
        },
      }),
    }

    chartWidget = new widget(widgetOptions)

    // Expose chartWidget globally for external access
    window.tradingViewChart = chartWidget

    if (chartWidget) {
      chartWidget.onChartReady(() => {
        if (chartWidget) {
          chartWidget.setDebugMode(widgetOptions.debug || false)

          // Register IHM Controller tool when chart is ready
          ihmController.registerTool(displayStockChartSchema, displayStockChartHandler)

          chartWidget.headerReady().then(() => {
            if (chartWidget) {
              const button = chartWidget.createButton()

              button.setAttribute('title', 'Click to show a notification popup')
              button.classList.add('apply-common-tooltip')

              button.addEventListener('click', () => {
                if (chartWidget) {
                  const message = props.enableTrading
                    ? 'Trading functionality is enabled with mock broker terminal!'
                    : 'Charting Library API works correctly'
                  chartWidget.showNoticeDialog({
                    title: 'Status',
                    body: message,
                    callback: () => {
                      console.log('Status checked!')
                    },
                  })
                }
              })

              button.innerHTML = props.enableTrading ? 'Trading Status' : 'Check API'
            }
          })
        }
      })
    }
  } catch (error) {
    console.error('Failed to initialize chart:', error)
  }
})

onUnmounted(async () => {
  // Unregister IHM Controller tool
  await ihmController.unregisterTool('displayStockChart')

  if (brokerService) {
    await brokerService.destroy()
    brokerService = null
  }

  if (chartWidget !== null) {
    chartWidget.remove()
    chartWidget = null
    // Clean up global reference
    window.tradingViewChart = null
  }
})
</script>

<style scoped>
.trader-chart-container {
  margin: 0 auto;
  padding: 10px;
  border: 1px solid rgba(84, 84, 84, 0.48);
  border-radius: 8px;
  background: #181818;
}

.trader-chart-container h3 {
  margin-top: 0;
  color: rgba(235, 235, 235, 0.64);
  text-align: center;
}

.chart-wrapper {
  background: transparent;
  border-radius: 4px;
  overflow: hidden;
}

.TVChartContainer {
  width: 100%;
  height: 850px;
}

@media (max-width: 768px) {
  .trader-chart-container {
    padding: 10px;
  }

  .TVChartContainer {
    height: 400px;
  }
}
</style>
