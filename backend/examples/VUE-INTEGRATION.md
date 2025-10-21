# Vue.js Client Integration

This directory contains an example of how to integrate the generated TypeScript client with a Vue.js application.

## Setup

1. Generate the client:
```bash
cd /path/to/trading-api
make clients
```

2. Copy the generated client to your Vue.js project:
```bash
cp -r clients/vue-client/src/* your-vue-project/src/api/
```

3. Install axios in your Vue.js project:
```bash
npm install axios
```

## Usage Example

```typescript
// src/services/TradingApiService.ts
import { Configuration, HealthApi } from '@/api'

const config = new Configuration({
  basePath: 'http://localhost:8000/api/v1'
})

export class TradingApiService {
  private healthApi: HealthApi

  constructor() {
    this.healthApi = new HealthApi(config)
  }

  async checkHealth() {
    try {
      const response = await this.healthApi.getHealthStatus()
      return response.data
    } catch (error) {
      console.error('Health check failed:', error)
      throw error
    }
  }
}
```

```vue
<!-- src/components/HealthCheck.vue -->
<template>
  <div class="health-check">
    <h2>API Health Status</h2>
    <div v-if="loading">Checking...</div>
    <div v-else-if="health" class="health-status">
      <p>Status: {{ health.status }}</p>
      <p>Message: {{ health.message }}</p>
      <p>Timestamp: {{ health.timestamp }}</p>
    </div>
    <div v-else class="error">Failed to check health</div>
    <button @click="checkHealth">Refresh</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { TradingApiService } from '@/services/TradingApiService'

const apiService = new TradingApiService()
const health = ref(null)
const loading = ref(false)

const checkHealth = async () => {
  loading.value = true
  try {
    health.value = await apiService.checkHealth()
  } catch (error) {
    console.error('Health check failed:', error)
    health.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  checkHealth()
})
</script>
```

## Features

The generated client provides:
- **Type Safety**: Full TypeScript support with auto-completion
- **Automatic Serialization**: Request/response transformation
- **Error Handling**: Structured error responses
- **Configuration**: Easy API endpoint and authentication setup
- **Interceptors**: Request/response middleware support
