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
import { widget } from '@public/trading_terminal'
import type {
  IChartingLibraryWidget,
  ResolutionString,
  LanguageCode,
  ChartingLibraryWidgetOptions,
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
    const widgetOptions: ChartingLibraryWidgetOptions = {
      symbol: props.symbol,
      datafeed: new DatafeedService(),
      interval: props.interval as ResolutionString,
      container: chartContainer.value,
      library_path: props.libraryPath,

      locale: getLanguageFromURL() || 'en',
      enabled_features: ['use_localstorage_for_settings'],
      disabled_features: ['study_templates'],
      // enabled_features: ['study_templates'], // Removed since we're disabling study_templates
      // charts_storage_url: props.chartsStorageUrl,
      // charts_storage_api_version: props.chartsStorageApiVersion as AvailableSaveloadVersions,
      // client_id: props.clientId,
      // user_id: props.userId,
      fullscreen: props.fullscreen,
      autosize: props.autosize,
      studies_overrides: props.studiesOverrides,
    }

    chartWidget = new widget(widgetOptions)

    // Expose chartWidget globally for external access
    window.tradingViewChart = chartWidget

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
                    body: 'Charting Library API works correctly',
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
  width: 100%;
  height: 600px;
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
