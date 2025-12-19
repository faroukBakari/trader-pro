/**
 * Error class hierarchy for centralized error management.
 * All application errors should extend AppError to ensure consistent handling.
 */

export type ErrorSeverity = 'error' | 'warning' | 'info'

/**
 * Abstract base class for all application errors.
 * Provides consistent structure for error handling and toast display.
 */
export abstract class AppError extends Error {
    abstract readonly code: string
    abstract readonly severity: ErrorSeverity
    abstract readonly userMessage: string
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
    readonly userMessage: string
    readonly topic: string
    readonly recoverable: boolean

    constructor(
        topic: string,
        code: string,
        userMessage: string,
        recoverable: boolean = false,
        details?: Record<string, unknown>,
    ) {
        super(`[${code}] ${userMessage}`, details)
        this.topic = topic
        this.code = code
        this.userMessage = userMessage
        this.recoverable = recoverable
        this.severity = recoverable ? 'warning' : 'error'
    }
}

/**
 * Network/API errors for REST call failures.
 */
export class NetworkError extends AppError {
    readonly code: string
    readonly severity: ErrorSeverity = 'error'
    readonly userMessage: string
    readonly statusCode?: number

    constructor(
        message: string,
        statusCode?: number,
        details?: Record<string, unknown>,
    ) {
        super(message, details)
        this.statusCode = statusCode
        this.code = statusCode ? `HTTP_${statusCode}` : 'NETWORK_ERROR'
        this.userMessage = message
    }
}

/**
 * Authentication errors (401/403).
 * These typically trigger redirect to login, no toast shown.
 */
export class AuthError extends AppError {
    readonly code: string = 'AUTH_ERROR'
    readonly severity: ErrorSeverity = 'error'
    readonly userMessage: string

    constructor(message: string = 'Authentication required', details?: Record<string, unknown>) {
        super(message, details)
        this.userMessage = message
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
    readonly userMessage: string
    readonly fieldErrors?: Record<string, string>

    constructor(
        message: string,
        fieldErrors?: Record<string, string>,
        details?: Record<string, unknown>,
    ) {
        super(message, details)
        this.userMessage = message
        this.fieldErrors = fieldErrors
    }

    /** Validation errors are shown inline, not via toast */
    override get showToast(): boolean {
        return false
    }
}
