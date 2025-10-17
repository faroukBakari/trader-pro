/**
 * Quick integration test for the API service wrapper
 * This tests that the wrapper correctly interfaces with the generated client
 */

import { ApiService } from '@/services/apiService'

export async function testApiIntegration() {
  console.log('🧪 Testing API Service Integration...')

  try {
    const apiService = new ApiService()
    console.log('📡 Testing health endpoint...')
    const health = await apiService.getHealthStatus()
    console.log('✅ Health check successful:', {
      status: health.status,
      api_version: health.api_version,
      timestamp: health.timestamp,
    })

    console.log('📡 Testing versions endpoint...')
    const versions = await apiService.getAPIVersions()
    console.log('✅ Versions check successful:', {
      current_version: versions.current_version,
      available_versions_count: versions.available_versions.length,
      documentation_url: versions.documentation_url,
    })

    console.log('🎉 All API service tests passed!')
    return true
  } catch (error) {
    console.error('❌ API service test failed:', error)

    // Check if it's a connection error (API not running)
    if (error instanceof Error && error.message.includes('ECONNREFUSED')) {
      console.log('💡 Note: Make sure the backend API is running on http://localhost:8000')
    }
    return false
  }
}
