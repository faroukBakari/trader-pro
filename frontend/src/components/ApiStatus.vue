<template>
  <div
    class="api-status-overlay"
    @mouseenter="cancelCollapseTimer"
    @mouseleave="startCollapseTimer"
  >
    <!-- Collapsed pill -->
    <button
      v-if="!isExpanded"
      class="status-pill"
      @click="togglePanel"
      :title="overallStatusText"
      aria-label="API Status"
    >
      <span class="status-dot" :class="`status-${overallStatus}`" />
      <span class="pill-label">API</span>
    </button>

    <!-- Expanded panel -->
    <div v-else class="status-panel" @keydown.esc="closePanel" tabindex="-1">
      <div class="panel-header">
        <h3>API Status</h3>
        <span class="client-badge">{{ clientType }}</span>
        <button class="close-btn" @click="closePanel" aria-label="Close">&times;</button>
      </div>

      <div v-if="initialLoading" class="panel-loading">Checking services...</div>

      <div v-else class="modules-list">
        <div v-for="module in moduleInfos" :key="module.name" class="module-row">
          <span class="status-dot" :class="getHealthClass(module.name)" />
          <span class="module-name">{{ module.displayName }}</span>
          <span class="module-status">{{ getHealthStatus(module.name) }}</span>
          <span v-if="getResponseTime(module.name) !== 'N/A'" class="response-time">
            {{ getResponseTime(module.name) }}
          </span>
        </div>

        <!-- Module links section -->
        <div class="module-links">
          <template v-for="module in moduleInfos" :key="`links-${module.name}`">
            <a :href="module.docsUrl" target="_blank" class="module-link">
              {{ module.displayName }} Docs
            </a>
          </template>
        </div>
      </div>

      <button class="refresh-btn" @click="refreshAll" :disabled="refreshing">
        {{ refreshing ? 'Refreshing...' : '↻ Refresh' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ApiService } from '@/services/apiService'
import type { ModuleHealth } from '@/types/apiStatus'

const apiService = new ApiService()

// Static module configuration (never changes)
const moduleInfos = ApiService.getIntegratedModules()

// Reactive state for module data
const modulesHealth = ref<Map<string, ModuleHealth>>(new Map())
const initialLoading = ref(true)
const refreshing = ref(false)
const clientType = ref<'server' | 'mock' | 'unknown'>('unknown')

// Expand/collapse state
const isExpanded = ref(false)
let collapseTimer: ReturnType<typeof setTimeout> | undefined

const overallStatus = computed<'ok' | 'error' | 'unknown'>(() => {
  if (initialLoading.value) return 'unknown'

  // Check health entries directly (single source of truth)
  const healthEntries = Array.from(modulesHealth.value.values())
  const hasError = healthEntries.some((h) => h.error !== null || h.health?.status !== 'ok')
  if (hasError) return 'error'

  const allOk = healthEntries.every((h) => h.health?.status === 'ok')
  return allOk ? 'ok' : 'unknown'
})

const overallStatusText = computed(() => {
  if (overallStatus.value === 'ok') return 'All systems operational'
  if (overallStatus.value === 'error') return 'Some services have issues'
  return 'Checking status...'
})

const togglePanel = () => {
  isExpanded.value = !isExpanded.value
}

const closePanel = () => {
  isExpanded.value = false
}

const startCollapseTimer = () => {
  cancelCollapseTimer() // Clear any existing timer first
  collapseTimer = setTimeout(closePanel, 3000)
}

const cancelCollapseTimer = () => {
  if (collapseTimer) {
    clearTimeout(collapseTimer)
    collapseTimer = undefined
  }
}

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

// Fetch all data
const fetchData = async () => {
  try {
    const health = await apiService.getAllModulesHealth()
    modulesHealth.value = health
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

onUnmounted(() => {
  if (collapseTimer) clearTimeout(collapseTimer)
})
</script>

<style scoped>
.api-status-overlay {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 1000;
  font-family:
    Inter,
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    sans-serif;
}

/* === Collapsed Pill === */
.status-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: rgba(24, 24, 24, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(84, 84, 84, 0.48);
  border-radius: 20px;
  color: rgba(235, 235, 235, 0.9);
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
  outline: none;
}

.status-pill:hover {
  background: rgba(34, 34, 34, 0.95);
  border-color: rgba(84, 84, 84, 0.65);
  transform: scale(1.05);
}

.status-pill:focus-visible {
  box-shadow: 0 0 0 2px #448aff;
}

.pill-label {
  text-transform: uppercase;
}

/* === Status Dots === */
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.status-ok {
  background: #00c853;
  box-shadow: 0 0 6px rgba(0, 200, 83, 0.4);
}

.status-error {
  background: #ff5252;
  box-shadow: 0 0 6px rgba(255, 82, 82, 0.4);
}

.status-unknown {
  background: #ffc107;
  box-shadow: 0 0 6px rgba(255, 193, 7, 0.3);
}

/* === Expanded Panel === */
.status-panel {
  width: 320px;
  max-height: 420px;
  overflow-y: auto;
  background: rgba(24, 24, 24, 0.88);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(84, 84, 84, 0.48);
  border-radius: 12px;
  padding: 16px;
  color: rgba(235, 235, 235, 0.9);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  animation: slideUp 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  will-change: transform, opacity;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Panel header */
.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(84, 84, 84, 0.32);
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: rgba(235, 235, 235, 0.9);
  flex: 1;
}

.client-badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(68, 138, 255, 0.15);
  color: #448aff;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.close-btn {
  background: none;
  border: none;
  color: rgba(235, 235, 235, 0.5);
  cursor: pointer;
  font-size: 16px;
  padding: 0 4px;
  line-height: 1;
  transition: color 0.2s;
}

.close-btn:hover {
  color: rgba(235, 235, 235, 0.9);
}

/* Panel loading */
.panel-loading {
  text-align: center;
  padding: 20px 0;
  color: rgba(235, 235, 235, 0.5);
  font-size: 13px;
}

/* Module rows */
.modules-list {
  display: flex;
  flex-direction: column;
}

.module-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid rgba(84, 84, 84, 0.24);
}

.module-row:last-of-type {
  border-bottom: none;
}

.module-name {
  font-size: 13px;
  font-weight: 500;
  color: rgba(235, 235, 235, 0.9);
  flex: 1;
}

.module-status {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  color: rgba(235, 235, 235, 0.64);
}

.response-time {
  font-size: 11px;
  color: rgba(235, 235, 235, 0.4);
  font-variant-numeric: tabular-nums;
}

/* Module links */
.module-links {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding-top: 10px;
  margin-top: 4px;
  border-top: 1px solid rgba(84, 84, 84, 0.24);
}

.module-link {
  font-size: 11px;
  color: #448aff;
  text-decoration: none;
  padding: 3px 8px;
  border-radius: 4px;
  background: rgba(68, 138, 255, 0.08);
  transition: background 0.2s;
}

.module-link:hover {
  background: rgba(68, 138, 255, 0.18);
}

/* Refresh button */
.refresh-btn {
  display: block;
  width: 100%;
  margin-top: 12px;
  padding: 8px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(68, 138, 255, 0.12);
  color: #448aff;
  border: 1px solid rgba(68, 138, 255, 0.2);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover:not(:disabled) {
  background: rgba(68, 138, 255, 0.22);
}

.refresh-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Scrollbar for panel */
.status-panel::-webkit-scrollbar {
  width: 4px;
}

.status-panel::-webkit-scrollbar-track {
  background: transparent;
}

.status-panel::-webkit-scrollbar-thumb {
  background: rgba(84, 84, 84, 0.4);
  border-radius: 2px;
}
</style>
