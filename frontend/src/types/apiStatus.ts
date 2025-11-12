import type { APIMetadata, HealthResponse } from '@/plugins/apiAdapter'

/**
 * Per-module health tracking
 */
export interface ModuleHealth {
    moduleName: string
    health: HealthResponse | null
    loading: boolean
    error: string | null
    responseTime?: number
}

/**
 * Per-module version tracking
 */
export interface ModuleVersions {
    moduleName: string
    versions: APIMetadata | null
    loading: boolean
    error: string | null
}

/**
 * Module registry information
 */
export interface ModuleInfo {
    name: string
    displayName: string
    docsUrl: string
    hasWebSocket: boolean
}
