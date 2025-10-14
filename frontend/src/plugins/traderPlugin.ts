/**
 * TraderPlugin Singleton
 * Centralized plugin manager for trading functionality
 */
export class ApiTraderPlugin<Features> {
  private static clientPromise: Promise<unknown> | null = null
  private static clientType: 'server' | 'mock' | 'unknown' = 'unknown'

  /**
   * Get the singleton instance
   */
  public async getClientWithFallback(Fallback: new () => Features): Promise<Features> {
    if (!ApiTraderPlugin.clientPromise) {
      // Use dynamic path construction to avoid Vite's static analysis
      const modulePath = '../clients/trader-client-generated/'

      ApiTraderPlugin.clientPromise = import(/* @vite-ignore */ modulePath)
        .then(({ V1Api, Configuration }) => {
          const basePath = import.meta.env.TRADER_API_BASE_PATH || ''
          const configuration = new Configuration({ basePath })
          const apiInstance = new V1Api(configuration)
          ApiTraderPlugin.clientType = 'server'
          console.info('✅ Generated API client loaded successfully')
          return apiInstance as unknown as Features
        })
        .catch((importError) => {
          console.warn(
            `⚠️ Generated client not available: ${importError.message}. => Using fallback API client`,
          )
          ApiTraderPlugin.clientType = 'mock'
          return Promise.resolve(new Fallback())
        })
    }
    return ApiTraderPlugin.clientPromise as Promise<Features>
  }

  static getApiClientType(): 'server' | 'mock' | 'unknown' {
    return ApiTraderPlugin.clientType
  }
}

/**
 * WebSocketClientPlugin Singleton
 * Centralized plugin manager for WebSocket client functionality
 */
export class WebSocketClientPlugin<Features> {
  private static clientPromise: Promise<unknown> | null = null
  private static factoryType: 'server' | 'mock' | 'unknown' = 'unknown'

  /**
   * Get the WebSocket client factory with fallback
   */
  public async getClientWithFallback(Fallback: new () => Features): Promise<Features> {
    if (!WebSocketClientPlugin.clientPromise) {
      const modulePath = '../clients/ws-generated/client'

      WebSocketClientPlugin.clientPromise = import(/* @vite-ignore */ modulePath)
        .then(({ BarsWebSocketClientFactory }) => {
          WebSocketClientPlugin.factoryType = 'server'
          console.info('✅ Generated WebSocket client loaded successfully')
          return BarsWebSocketClientFactory()
        })
        .catch((importError) => {
          console.warn(
            `⚠️ Generated WebSocket client not available: ${importError.message}. => Using fallback WebSocket client`,
          )
          WebSocketClientPlugin.factoryType = 'mock'
          return Promise.resolve(Fallback)
        })
    }
    return WebSocketClientPlugin.clientPromise as Promise<Features>
  }

  static getWsClientType(): 'server' | 'mock' | 'unknown' {
    return WebSocketClientPlugin.factoryType
  }
}
