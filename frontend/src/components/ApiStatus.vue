<template>
  <div class="api-status">
    <h3>API Status</h3>
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
            <li v-for="version in versionsData.versions" :key="version.version">
              {{ version.version }} - {{ version.status }}
              <span v-if="version.deprecated" class="deprecated">(deprecated)</span>
            </li>
          </ul>
        </div>
      </div>
    </div>

    <button @click="refreshData" :disabled="healthLoading || versionsLoading">Refresh</button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { apiService, type HealthResponse, type ApiVersionsResponse } from '@/services/api'

// Health check state
const healthData = ref<HealthResponse | null>(null)
const healthLoading = ref(false)
const healthError = ref<string | null>(null)

// Versions state
const versionsData = ref<ApiVersionsResponse | null>(null)
const versionsLoading = ref(false)
const versionsError = ref<string | null>(null)

const fetchHealth = async () => {
  healthLoading.value = true
  healthError.value = null
  try {
    healthData.value = await apiService.getHealth()
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
    versionsData.value = await apiService.getVersions()
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
