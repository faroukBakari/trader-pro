/**
 * Error management module exports.
 * Provides centralized error handling via ErrorService and typed error classes.
 */

export {
    AppError,
    AuthError,
    NetworkError,
    ValidationError,
    WebSocketError,
    type ErrorSeverity
} from './classes'
export { errorService } from './errorService'

