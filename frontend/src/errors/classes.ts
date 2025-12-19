/**
 * Error class hierarchy for centralized error management.
 * All application errors should extend AppError to ensure consistent handling.
 */

import type { SubscriptionError } from '@/plugins/wsClientBase'

export type ErrorSeverity = 'error' | 'warning' | 'info'

/**
 * Abstract base class for all application errors.
 * Provides consistent structure for error handling and toast display.
 * The inherited `message` property is used for toast display (technical format).
 */
export abstract class AppError extends Error {
    abstract readonly code: string
    abstract readonly severity: ErrorSeverity
    readonly timestamp: number = Date.now()
    readonly details?: Record<string, unknown>

    constructor(message: string, details?: Record<string, unknown>) {
        super(message)
        this.name = this.constructor.name
        this.details = details
    }

    /** Controls whether toast is shown. Override to disable for specific error types. */
    get showToast(): boolean {
        return true
    }
}

/**
 * WebSocket subscription errors.
 * Created from SubscriptionError payloads received via WebSocket.
 */
export class WebSocketError extends AppError {
    readonly code: string
    readonly severity: ErrorSeverity
    readonly topic: string
    readonly recoverable: boolean

    constructor(
        topic: string,
        code: string,
        message: string,
        recoverable: boolean = false,
        details?: Record<string, unknown>,
    ) {
        super(`[${code}] ${message}`, details)
        this.topic = topic
        this.code = code
        this.recoverable = recoverable
        this.severity = recoverable ? 'warning' : 'error'
    }

    /**
     * Factory method to create WebSocketError from raw SubscriptionError payload.
     * Single source of truth for SubscriptionError → WebSocketError conversion.
     *
     * @param error - Raw subscription error from backend
     * @param context - Optional context like subscription name for enriched messages
     */
    static fromSubscription(
        error: SubscriptionError,
        context?: { subscriptionName?: string },
    ): WebSocketError {
        const prefix = context?.subscriptionName ? `${context.subscriptionName}: ` : ''
        return new WebSocketError(
            error.topic,
            error.error.code,
            `${prefix}${error.error.message}`,
            error.recoverable ?? false,
            {
                ...error.error.details,
                ...(context?.subscriptionName && { subscriptionName: context.subscriptionName }),
            },
        )
    }
}

/**
 * Network/API errors for REST call failures.
 */
export class NetworkError extends AppError {
    readonly code: string
    readonly severity: ErrorSeverity = 'error'
    readonly statusCode?: number

    constructor(
        message: string,
        statusCode?: number,
        details?: Record<string, unknown>,
    ) {
        super(message, details)
        this.statusCode = statusCode
        this.code = statusCode ? `HTTP_${statusCode}` : 'NETWORK_ERROR'
    }
}

/**
 * Authentication errors (401/403).
 * These typically trigger redirect to login, no toast shown.
 */
export class AuthError extends AppError {
    readonly code: string = 'AUTH_ERROR'
    readonly severity: ErrorSeverity = 'error'

    constructor(message: string = 'Authentication required', details?: Record<string, unknown>) {
        super(message, details)
    }

    /** Auth errors redirect to login, don't show toast */
    override get showToast(): boolean {
        return false
    }
}

/**
 * Validation errors for form/input validation.
 * Shown inline in forms, no toast.
 */
export class ValidationError extends AppError {
    readonly code: string = 'VALIDATION_ERROR'
    readonly severity: ErrorSeverity = 'warning'
    readonly fieldErrors?: Record<string, string>

    constructor(
        message: string,
        fieldErrors?: Record<string, string>,
        details?: Record<string, unknown>,
    ) {
        super(message, details)
        this.fieldErrors = fieldErrors
    }

    /** Validation errors are shown inline, not via toast */
    override get showToast(): boolean {
        return false
    }
}
