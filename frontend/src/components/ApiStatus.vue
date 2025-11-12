<template>
  <div class="api-status">
    <header>
      <h2>API Status</h2>
      <span
        >Client: <strong>{{ clientType }}</strong></span
      >
    </header>

    <p v-if="initialLoading" class="loading">Loading API status...</p>

    <div v-else class="modules-grid">
      <article v-for="module in moduleInfos" :key="module.name" class="module-card">
        <h3>{{ module.displayName }}</h3>

        <dl>
          <div class="row">
            <dt>Health:</dt>
            <dd :class="['status', getHealthClass(module.name)]">
              {{ getHealthStatus(module.name) }}
            </dd>
          </div>

          <div v-if="getHealthError(module.name)" class="error">
            {{ getHealthError(module.name) }}
          </div>

          <template v-else-if="getHealth(module.name)">
            <div class="row">
              <dt>Version:</dt>
              <dd>{{ getHealth(module.name)?.api_version || 'N/A' }}</dd>
            </div>
            <div class="row">
              <dt>Response Time:</dt>
              <dd>{{ getResponseTime(module.name) }}</dd>
            </div>
            <div class="row">
              <dt>Current Version:</dt>
              <dd>{{ getCurrentVersion(module.name) }}</dd>
            </div>
          </template>

          <div v-else-if="getVersionsError(module.name)" class="error">
            {{ getVersionsError(module.name) }}
          </div>
        </dl>

        <nav>
          <a :href="module.docsUrl" target="_blank">📚 OpenAPI Docs</a>
          <a
            v-if="module.hasWebSocket"
            :href="`/api/v1/${module.name}/ws/asyncapi`"
            target="_blank"
          >
            📡 AsyncAPI Spec
          </a>
        </nav>
      </article>
    </div>

    <button @click="refreshAll" :disabled="refreshing">
      {{ refreshing ? 'Refreshing...' : 'Refresh All' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ApiService } from '@/services/apiService'
import type { ModuleHealth, ModuleVersions } from '@/types/apiStatus'

const apiService = new ApiService()

// Static module configuration (never changes)
const moduleInfos = ApiService.getIntegratedModules()

// Reactive state for module data
const modulesHealth = ref<Map<string, ModuleHealth>>(new Map())
const modulesVersions = ref<Map<string, ModuleVersions>>(new Map())
const initialLoading = ref(true)
const refreshing = ref(false)
const clientType = ref<'server' | 'mock' | 'unknown'>('unknown')

// Getter functions for reactive access
const getHealth = (moduleName: string) => modulesHealth.value.get(moduleName)?.health ?? null

const getHealthError = (moduleName: string) => modulesHealth.value.get(moduleName)?.error ?? null

const getHealthStatus = (moduleName: string): string => {
  const error = getHealthError(moduleName)
  if (error) return 'Error'
  return getHealth(moduleName)?.status || 'Unknown'
}

const getHealthClass = (moduleName: string): string => {
  if (getHealthError(moduleName)) return 'status-error'
  if (getHealth(moduleName)?.status === 'ok') return 'status-ok'
  return 'status-unknown'
}

const getResponseTime = (moduleName: string): string => {
  const time = modulesHealth.value.get(moduleName)?.responseTime
  return time !== undefined ? `${time}ms` : 'N/A'
}

const getVersionsError = (moduleName: string) =>
  modulesVersions.value.get(moduleName)?.error ?? null

const getCurrentVersion = (moduleName: string): string => {
  return modulesVersions.value.get(moduleName)?.versions?.current_version || 'N/A'
}

// Fetch all data
const fetchData = async () => {
  try {
    const [health, versions] = await Promise.all([
      apiService.getAllModulesHealth(),
      apiService.getAllModulesVersions(),
    ])

    modulesHealth.value = health
    modulesVersions.value = versions
    clientType.value = apiService.getClientType()
  } catch (error) {
    console.error('Failed to fetch API status:', error)
  }
}

const refreshAll = async () => {
  refreshing.value = true
  try {
    await fetchData()
  } finally {
    refreshing.value = false
  }
}

onMounted(async () => {
  await fetchData()
  initialLoading.value = false
})
</script>

<style scoped>
.api-status {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

header span {
  font-size: 14px;
  color: #666;
}

.loading {
  text-align: center;
  padding: 40px;
  color: #666;
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 400px));
  gap: 20px;
  margin-bottom: 20px;
  justify-content: center;
}

.module-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 20px;
  background: #fff;
}

.module-card h3 {
  margin: 0 0 20px 0;
  font-size: 20px;
  color: #333;
  border-bottom: 2px solid #007bff;
  padding-bottom: 8px;
}

dl {
  font-size: 14px;
  background: #f8f9fa;
  padding: 4px;
  border-radius: 4px;
  margin: 0 0 10px 0;
}

.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
}

dt {
  font-weight: 600;
  color: #666;
}

dd {
  margin: 0;
  color: #333;
  font-weight: 500;
}

.status {
  padding: 4px 12px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 12px;
}

.status-ok {
  background: #d4edda;
  color: #155724;
}

.status-error {
  background: #f8d7da;
  color: #721c24;
}

.status-unknown {
  background: #fff3cd;
  color: #856404;
}

.error {
  padding: 8px 12px;
  background: #f8d7da;
  border-left: 3px solid #dc3545;
  border-radius: 4px;
  font-size: 13px;
  color: #721c24;
  margin-top: 8px;
}

nav {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px solid #eee;
}

nav a {
  padding: 6px 12px;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 13px;
  transition: background 0.2s;
}

nav a:hover {
  background: #0056b3;
}

button {
  display: block;
  margin: 0 auto;
  padding: 10px 24px;
  font-size: 16px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

button:hover:not(:disabled) {
  background: #218838;
}

button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}
</style>
