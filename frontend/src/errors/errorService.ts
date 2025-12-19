/**
 * Centralized error handling service.
 * Converts unknown errors to AppError and displays toasts via vue-sonner.
 */

import type { SubscriptionError } from '@/plugins/wsClientBase'
import { toast } from 'vue-sonner'
import { AppError, NetworkError, WebSocketError } from './classes'

/**
 * Type guard for SubscriptionError shape (raw WebSocket error payload).
 */
function isSubscriptionError(error: unknown): error is SubscriptionError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'topic' in error &&
    'error' in error &&
    typeof (error as SubscriptionError).error?.code === 'string' &&
    typeof (error as SubscriptionError).error?.message === 'string'
  )
}

interface ErrorServiceConfig {
  /** Duration in ms for toast display (default: 5000) */
  defaultDuration: number
  /** Maximum concurrent toasts (default: 5) */
  maxToasts: number
  /** Dedupe window in ms - errors with same code within this window are not shown twice */
  dedupeWindowMs: number
}

const DEFAULT_CONFIG: ErrorServiceConfig = {
  defaultDuration: 6000,
  maxToasts: 1,
  dedupeWindowMs: 2000,
}

class ErrorService {
  private config: ErrorServiceConfig
  private recentErrors: Map<string, number> = new Map()

  constructor(config: Partial<ErrorServiceConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config }
  }

  /**
   * Main entry point for error handling.
   * Converts unknown errors to AppError and displays toast if appropriate.
   */
  handle(error: unknown): void {
    try {
      const appError = this.fromUnknown(error)

      // Always log full error details
      // console.error(`[ErrorService] ${appError.code}:`, appError.message, appError.details ?? '')

      // Check if toast should be shown
      if (!appError.showToast) {
        return
      }

      // Dedupe check - don't spam same error
      if (this.isDuplicate(appError.code)) {
        console.debug(`[ErrorService] Suppressing duplicate error: ${appError.code}`)
        return
      }

      this.showToast(appError)
    } catch (handlerError) {
      // Fallback if error handler itself fails
      console.error('[ErrorService] Error in error handler:', handlerError)
      console.error('[ErrorService] Original error:', error)
    }
  }

  /**
   * Convert any error type to AppError.
   */
  fromUnknown(error: unknown): AppError {
    // Already an AppError
    if (error instanceof AppError) {
      return error
    }

    // Raw SubscriptionError from WebSocket (not yet wrapped)
    if (isSubscriptionError(error)) {
      const { code, message, details } = error.error
      const detailsSuffix = details ? ` ${JSON.stringify(details)}` : ''
      return new WebSocketError(
        error.topic,
        code,
        `[${code}] ${message} ${detailsSuffix}`,
        error.recoverable ?? false,
        details ?? undefined,
      )
    }

    // Standard Error
    if (error instanceof Error) {
      return new NetworkError(error.message)
    }

    // String error
    if (typeof error === 'string') {
      return new NetworkError(error)
    }

    // Object with message property
    if (error && typeof error === 'object' && 'message' in error) {
      const msg = (error as { message: unknown }).message
      return new NetworkError(typeof msg === 'string' ? msg : 'Unknown error')
    }

    // Fallback
    return new NetworkError('An unexpected error occurred')
  }

  /**
   * Check if error code was recently shown (within dedupe window).
   */
  private isDuplicate(code: string): boolean {
    const now = Date.now()
    const lastShown = this.recentErrors.get(code)

    if (lastShown && now - lastShown < this.config.dedupeWindowMs) {
      return true
    }

    this.recentErrors.set(code, now)

    // Cleanup old entries
    if (this.recentErrors.size > 100) {
      const cutoff = now - this.config.dedupeWindowMs
      for (const [key, timestamp] of this.recentErrors.entries()) {
        if (timestamp < cutoff) {
          this.recentErrors.delete(key)
        }
      }
    }

    return false
  }

  /**
   * Display toast based on error severity.
   * Shows only the message - no icons, buttons, or descriptions.
   */
  private showToast(error: AppError): void {
    const options = {
      duration: this.config.defaultDuration,
    }

    switch (error.severity) {
      case 'error':
        toast.error(error.message, options)
        break
      case 'warning':
        toast.warning(error.message, options)
        break
      case 'info':
        toast.info(error.message, options)
        break
    }
  }
}

// Export singleton instance
export const errorService = new ErrorService()
