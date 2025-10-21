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
import { widget } from '@public/trading_terminal'
import type {
  IChartingLibraryWidget,
  ResolutionString,
  LanguageCode,
  TradingTerminalWidgetOptions,
  IBrokerConnectionAdapterHost,
} from '@public/trading_terminal'

function getLanguageFromURL() {
  const regex = new RegExp('[\\?&]lang=([^&#]*)')
  const results = regex.exec(window.location.search)
  return results === null
    ? null
    : (decodeURIComponent(results[1].replace(/\+/g, ' ')) as LanguageCode)
}

const props = defineProps({
  symbol: {
    default: 'AAPL',
    type: String,
  },
  interval: {
    default: '1D',
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
      symbol: props.symbol,
      datafeed,
      interval: props.interval as ResolutionString,
      container: chartContainer.value,
      library_path: props.libraryPath,

      locale: getLanguageFromURL() || 'en',
      theme: 'dark',
      // enabled_features: ['use_localstorage_for_settings'],
      disabled_features: ['study_templates', 'adaptive_logo'], // , 'use_localstorage_for_settings'

      // System color scheme overrides
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
      debug_broker: 'all', // BrokerDebugMode.All,

      // Trading functionality
      ...(props.enableTrading && {
        broker_factory: (host: IBrokerConnectionAdapterHost) => {
          return new BrokerTerminalService(host, datafeed)
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

onUnmounted(() => {
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
  height: 800px;
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
