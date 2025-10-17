<template>
  <div class="api-status">
    <h3>API Status</h3>

    <!-- Client Type Indicator -->
    <div class="client-type-indicator">
      <div v-if="clientType === 'server'" class="client-type server">
        🌐 Connected to Live Server
      </div>
      <div v-else-if="clientType === 'mock'" class="client-type mock">🎭 Using Mock Client</div>
      <div v-else class="client-type unknown">⏳ Checking Connection...</div>
    </div>

    <div class="status-grid">
      <div class="status-item">
        <h4>Health Check</h4>
        <div v-if="healthLoading" class="loading">Loading...</div>
        <div v-else-if="healthError" class="error">Error: {{ healthError }}</div>
        <div v-else-if="healthData" class="success">
          <p>Status: {{ healthData.status }}</p>
          <p>Version: {{ healthData.api_version }}</p>
          <p>Timestamp: {{ new Date(healthData.timestamp).toLocaleString() }}</p>
        </div>
      </div>

      <div class="status-item">
        <h4>API Versions</h4>
        <div v-if="versionsLoading" class="loading">Loading...</div>
        <div v-else-if="versionsError" class="error">Error: {{ versionsError }}</div>
        <div v-else-if="versionsData" class="success">
          <p>Current: {{ versionsData.current_version }}</p>
          <ul>
            <li v-for="version in versionsData.available_versions" :key="version.version">
              {{ version.version }} - {{ version.status }}
              <span v-if="version.deprecation_notice" class="deprecated">(deprecated)</span>
              <span v-if="version.sunset_date" class="sunset"
                >sunset: {{ new Date(version.sunset_date).toLocaleDateString() }}</span
              >
            </li>
          </ul>
          <p class="docs-link">
            <a :href="versionsData.documentation_url" target="_blank" rel="noopener"
              >📚 API Documentation</a
            >
          </p>
        </div>
      </div>
    </div>

    <button @click="refreshData" :disabled="healthLoading || versionsLoading">Refresh</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ApiService, type HealthResponse, type APIMetadata } from '@/services/apiService'

// Health check state
const healthData = ref<HealthResponse | null>(null)
const healthLoading = ref(false)
const healthError = ref<string | null>(null)

// Versions state
const versionsData = ref<APIMetadata | null>(null)
const versionsLoading = ref(false)
const versionsError = ref<string | null>(null)
const apiService = new ApiService()

// Client type state
const clientType = ref<'server' | 'mock' | 'unknown'>('unknown')

const fetchHealth = async () => {
  healthLoading.value = true
  healthError.value = null
  try {
    healthData.value = await apiService.getHealthStatus()
    // Update client type after successful call
    clientType.value = apiService.getClientType()
  } catch (error) {
    healthError.value = error instanceof Error ? error.message : 'Unknown error'
  } finally {
    healthLoading.value = false
  }
}

const fetchVersions = async () => {
  versionsLoading.value = true
  versionsError.value = null
  try {
    versionsData.value = await apiService.getAPIVersions()
    // Update client type after successful call
    clientType.value = apiService.getClientType()
  } catch (error) {
    versionsError.value = error instanceof Error ? error.message : 'Unknown error'
  } finally {
    versionsLoading.value = false
  }
}

const refreshData = async () => {
  await Promise.all([fetchHealth(), fetchVersions()])
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped>
.api-status {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.client-type-indicator {
  margin-bottom: 20px;
}

.client-type {
  display: inline-block;
  padding: 8px 16px;
  border-radius: 20px;
  font-weight: 500;
  font-size: 14px;
}

.client-type.server {
  background: #e8f5e8;
  color: #2e7d32;
  border: 1px solid #c8e6c9;
}

.client-type.mock {
  background: #fff3e0;
  color: #f57c00;
  border: 1px solid #ffcc02;
}

.client-type.unknown {
  background: #f5f5f5;
  color: #666;
  border: 1px solid #ddd;
}

.status-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 20px 0;
}

.status-item {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 15px;
  background: #f9f9f9;
}

.status-item h4 {
  margin-top: 0;
  color: #333;
}

.loading {
  color: #666;
  font-style: italic;
}

.error {
  color: #d32f2f;
  font-weight: bold;
}

.success {
  color: #2e7d32;
}

.success p {
  margin: 5px 0;
}

.success ul {
  margin: 10px 0;
  padding-left: 20px;
}

.deprecated {
  color: #f57c00;
  font-size: 0.8em;
}

.sunset {
  color: #d32f2f;
  font-size: 0.8em;
  margin-left: 8px;
}

.docs-link {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #ddd;
}

.docs-link a {
  color: #42b883;
  text-decoration: none;
}

.docs-link a:hover {
  text-decoration: underline;
}

button {
  background: #42b883;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

button:hover:not(:disabled) {
  background: #369870;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
