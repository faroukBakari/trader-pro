/**
 * TraderPlugin Singleton
 * Centralized plugin manager for trading functionality
 */
export class TraderPlugin<Features> {
  private static clientPromise: Promise<unknown> | null = null
  private static clientType: 'server' | 'mock' | 'unknown' = 'unknown'

  /**
   * Get the singleton instance
   */
  public async getClientWithFallback(Fallback: new () => Features): Promise<Features> {
    if (!TraderPlugin.clientPromise) {
      // Use dynamic path construction to avoid Vite's static analysis
      const modulePath = '../clients/trader-client-generated/'

      TraderPlugin.clientPromise = import(/* @vite-ignore */ modulePath)
        .then(({ V1Api, Configuration }) => {
          const basePath = import.meta.env.TRADER_API_BASE_PATH || ''
          const configuration = new Configuration({ basePath })
          const apiInstance = new V1Api(configuration)
          TraderPlugin.clientType = 'server'
          console.info('✅ Generated API client loaded successfully')
          return apiInstance as unknown as Features
        })
        .catch((importError) => {
          console.warn(
            `⚠️ Generated client not available: ${importError.message}. => Using fallback API client`,
          )
          TraderPlugin.clientType = 'mock'
          return Promise.resolve(new Fallback())
        })
    }
    return TraderPlugin.clientPromise as Promise<Features>
  }

  static getClientType(): 'server' | 'mock' | 'unknown' {
    return TraderPlugin.clientType
  }
}
