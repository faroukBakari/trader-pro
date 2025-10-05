<template>
  <div class="trader-chart-container">
    <h3>Trading Chart</h3>
    <div class="chart-wrapper">
      <div class="TVChartContainer" ref="chartContainer" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, onUnmounted } from 'vue'

// TradingView widget will be loaded from global window object
declare global {
  interface Window {
    TradingView: {
      widget: new (options: Record<string, unknown>) => TradingViewWidget
    }
  }
}

function getLanguageFromURL() {
  const regex = new RegExp('[\\?&]lang=([^&#]*)')
  const results = regex.exec(window.location.search)
  return results === null ? null : decodeURIComponent(results[1].replace(/\+/g, ' '))
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
  datafeedUrl: {
    default: 'https://demo_feed.tradingview.com',
    type: String,
  },
  libraryPath: {
    default: '/charting_library/',
    type: String,
  },
  chartsStorageUrl: {
    default: 'https://saveload.tradingview.com',
    type: String,
  },
  chartsStorageApiVersion: {
    default: '1.1',
    type: String,
  },
  clientId: {
    default: 'tradingview.com',
    type: String,
  },
  userId: {
    default: 'public_user_id',
    type: String,
  },
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
})

interface TradingViewWidget {
  onChartReady: (callback: () => void) => void
  headerReady: () => Promise<void>
  createButton: () => HTMLElement
  showNoticeDialog: (options: { title: string; body: string; callback: () => void }) => void
  remove: () => void
}

const chartContainer = ref<HTMLDivElement>()
let chartWidget: TradingViewWidget | null = null

onMounted(() => {
  if (!chartContainer.value) {
    console.error('Chart container element not found')
    return
  }

  try {
    const widgetOptions = {
      symbol: props.symbol,
      datafeed: {
        onReady: (callback: (config: unknown) => void) => {
          setTimeout(() => callback({}), 0)
        },
        searchSymbols: () => {},
        resolveSymbol: (
          symbolName: string,
          onSymbolResolvedCallback: (symbol: unknown) => void,
        ) => {
          setTimeout(
            () =>
              onSymbolResolvedCallback({
                name: symbolName,
                full_name: symbolName,
                description: symbolName,
                type: 'stock',
                session: '24x7',
                timezone: 'Etc/UTC',
                ticker: symbolName,
                minmov: 1,
                pricescale: 100,
                has_intraday: true,
                supported_resolutions: ['1', '5', '15', '30', '60', '240', '1D'],
                volume_precision: 2,
                data_status: 'streaming',
              }),
            0,
          )
        },
        getBars: () => {
          // Return empty bars for now
          return Promise.resolve({ bars: [], meta: { noData: true } })
        },
        subscribeBars: () => {},
        unsubscribeBars: () => {},
      },
      interval: props.interval,
      container: chartContainer.value,
      library_path: props.libraryPath,

      locale: getLanguageFromURL() || 'en',
      disabled_features: ['use_localstorage_for_settings'],
      enabled_features: ['study_templates'],
      charts_storage_url: props.chartsStorageUrl,
      charts_storage_api_version: props.chartsStorageApiVersion,
      client_id: props.clientId,
      user_id: props.userId,
      fullscreen: props.fullscreen,
      autosize: props.autosize,
      studies_overrides: props.studiesOverrides,
    }
    chartWidget = new window.TradingView.widget(widgetOptions)

    if (chartWidget) {
      chartWidget.onChartReady(() => {
        if (chartWidget) {
          chartWidget.headerReady().then(() => {
            if (chartWidget) {
              const button = chartWidget.createButton()

              button.setAttribute('title', 'Click to show a notification popup')
              button.classList.add('apply-common-tooltip')

              button.addEventListener('click', () => {
                if (chartWidget) {
                  chartWidget.showNoticeDialog({
                    title: 'Notification',
                    body: 'TradingView Charting Library API works correctly',
                    callback: () => {
                      console.log('Noticed!')
                    },
                  })
                }
              })

              button.innerHTML = 'Check API'
            }
          })
        }
      })
    }
  } catch (error) {
    console.error('Failed to initialize TradingView chart:', error)
  }
})

onUnmounted(() => {
  if (chartWidget !== null) {
    chartWidget.remove()
    chartWidget = null
  }
})
</script>

<style scoped>
.trader-chart-container {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #f9f9f9;
}

.trader-chart-container h3 {
  margin-top: 0;
  color: #333;
  text-align: center;
}

.chart-wrapper {
  background: #fff;
  border-radius: 4px;
  overflow: hidden;
}

.TVChartContainer {
  height: 400px;
  width: 100%;
}

@media (max-width: 768px) {
  .trader-chart-container {
    padding: 15px;
  }

  .TVChartContainer {
    height: 300px;
  }
}
</style>
