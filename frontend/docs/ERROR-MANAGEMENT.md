# Frontend Error Management

**Status**: ✅ Production Ready  
**Last Updated**: December 19, 2025  
**Version**: 1.0.0

---

## Table of Contents

- [Overview](#overview)
- [Error Handling Philosophy](#error-handling-philosophy)
- [Architecture](#architecture)
- [Error Class Hierarchy](#error-class-hierarchy)
- [ErrorService](#errorservice)
- [Global Handler Integration](#global-handler-integration)
- [Usage Patterns](#usage-patterns)
- [Toast Notifications](#toast-notifications)
- [WebSocket Error Integration](#websocket-error-integration)
- [Related Documentation](#related-documentation)

---

## Overview

The Trading Pro frontend implements a **centralized error handling system** that provides:

- **Global Error Capture**: Vue, window, and unhandled promise rejection handlers
- **Type-Safe Errors**: Class hierarchy with semantic error types
- **Toast Notifications**: User-friendly error display via vue-sonner
- **Deduplication**: Prevents error spam within configurable time window
- **Queue Management**: Respects max concurrent toasts with pending queue

---

## Error Handling Philosophy

### Core Principle: "Only Catch What You Can Handle"

> _"If unsure, let it throw. Let it crash. Log the error."_  
> — Industry best practice, inspired by Erlang's "Let It Crash" philosophy (Joe Armstrong)

**Exceptions are NOT caught within services or components** unless there is a **specific mitigation strategy**. Instead, they propagate naturally to the global error handler which:

- ✅ Displays user-friendly toast notifications
- ✅ Logs full error details for debugging
- ✅ Ensures consistent error handling across the application
- ✅ Keeps business logic clean and readable

### Decision Matrix: When to Catch Locally

```
┌────────────────────────────────────────────────────────────────┐
│                   CAN YOU MITIGATE?                            │
├──────────────────────┬─────────────────────────────────────────┤
│         YES          │                   NO                    │
├──────────────────────┼─────────────────────────────────────────┤
│ • Retry with backoff │ • Unknown/unexpected error              │
│ • Fallback value     │ • No recovery possible                  │
│ • Partial results    │ • User needs to know anyway             │
│ • User prompt/action │                                         │
├──────────────────────┼─────────────────────────────────────────┤
│   ✅ CATCH LOCALLY   │        ❌ LET IT PROPAGATE              │
│   (handle + recover) │   (global handler shows toast)          │
└──────────────────────┴─────────────────────────────────────────┘
```

### Anti-Patterns Avoided

| Anti-Pattern                   | Description                              | Our Approach                       |
| ------------------------------ | ---------------------------------------- | ---------------------------------- |
| **Pokémon Exception Handling** | "Gotta catch 'em all" — catch and ignore | ❌ Removed empty `.catch()` blocks |
| **Error Swallowing**           | `catch (e) { }` silently discards        | ❌ All errors reach global handler |
| **Defensive Overkill**         | try-catch on every line                  | ❌ Centralized handler instead     |
| **Log & Pray**                 | `catch (e) { console.log(e) }`           | ❌ Toast + structured logging      |
| **Cascaded Try-Catch**         | Nested try-catch everywhere              | ❌ Single boundary at global level |

### Why This Matters

Previous architecture had try-catch blocks scattered throughout services, which:

- Made debugging a nightmare (errors caught and re-thrown multiple times)
- Created inconsistent error handling behavior
- Obscured the actual error origin in stack traces
- Led to duplicate error logging

---

## Architecture

### Error Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      Error Sources                                │
├──────────────────────────────────────────────────────────────────┤
│  REST API         │  WebSocket        │  Vue Components          │
│  (NetworkError)   │  (SubscriptionError) │  (Lifecycle errors)   │
└────────┬──────────┴───────┬───────────┴────────────┬─────────────┘
         │                  │                        │
         │ throw            │ throw                  │ throw
         ▼                  ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Error Propagation Layer                        │
│                                                                  │
│  • No try-catch in services (errors bubble up naturally)         │
│  • @ApiErrorHandler decorator wraps API calls                    │
│  • WebSocket errors throw WebSocketError                         │
└──────────────────────────────────────────────────────────────────┘
         │                  │                        │
         ▼                  ▼                        ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Global Error Handlers (main.ts)                │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ app.config.errorHandler     → Vue component errors         │  │
│  │ window.onerror              → Uncaught JS errors           │  │
│  │ window.onunhandledrejection → Unhandled promise rejections │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   ErrorService.handle()                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 1. fromUnknown()  → Normalize to AppError                  │  │
│  │ 2. isDuplicate()  → Dedupe check (2s window)               │  │
│  │ 3. showToast()    → Queue management + display             │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   Toast Display (vue-sonner)                     │
│                   AppToaster.vue component                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Error Class Hierarchy

All application errors extend `AppError` for consistent handling.

```
AppError (abstract base)
├── WebSocketError    # Subscription errors from WebSocket
├── NetworkError      # REST API / HTTP errors
├── AuthError         # Authentication failures (no toast)
└── ValidationError   # Form validation (no toast, inline display)
```

### Class Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      AppError (abstract)                    │
│  ─────────────────────────────────────────────────────────  │
│  + code: string           # Machine-readable error code     │
│  + severity: ErrorSeverity # 'error' | 'warning' | 'info'   │
│  + message: string        # Human-readable (inherited)      │
│  + timestamp: number      # Unix timestamp                  │
│  + details?: Record       # Optional context                │
│  ─────────────────────────────────────────────────────────  │
│  + showToast: boolean     # Whether to display toast        │
└─────────────────────────────────────────────────────────────┘
         ▲            ▲            ▲            ▲
         │            │            │            │
┌────────┴───┐ ┌──────┴─────┐ ┌────┴────┐ ┌────┴──────────┐
│WebSocketErr│ │NetworkError│ │AuthError│ │ValidationError│
│────────────│ │────────────│ │─────────│ │───────────────│
│+topic      │ │+statusCode?│ │showToast│ │+fieldErrors?  │
│+recoverable│ │            │ │= false  │ │showToast=false│
│────────────│ │            │ │         │ │               │
│fromSubscr..│ │            │ │         │ │               │
└────────────┘ └────────────┘ └─────────┘ └───────────────┘
```

**Source:** [src/errors/classes.ts](../src/errors/classes.ts)

### WebSocketError

For subscription-level errors received via WebSocket.

```typescript
import { WebSocketError } from '@/errors'

// Direct construction
throw new WebSocketError(
  'orders:{"accountId":"TEST"}', // topic
  'PROVIDER_TIMEOUT', // code
  'Request timed out', // message
  true, // recoverable
  { provider: 'tws' }, // details
)

// Factory method (preferred) - from backend SubscriptionError
throw WebSocketError.fromSubscription(error, { subscriptionName: 'Orders' })
```

### NetworkError

For REST API and HTTP errors.

```typescript
import { NetworkError } from '@/errors'

throw new NetworkError(
  'Failed to fetch orders', // message
  500, // statusCode (optional)
  { endpoint: '/orders' }, // details (optional)
)
```

### AuthError

For authentication failures. Does NOT show toast (redirects to login instead).

```typescript
import { AuthError } from '@/errors'

throw new AuthError('Session expired')
// showToast = false → no toast displayed
```

### ValidationError

For form validation. Does NOT show toast (displayed inline in form).

```typescript
import { ValidationError } from '@/errors'

throw new ValidationError('Invalid input', { email: 'Invalid email format', password: 'Too short' })
// showToast = false → displayed inline in form
```

---

## ErrorService

Singleton service that handles all errors and manages toast display.

**Source:** [src/errors/errorService.ts](../src/errors/errorService.ts)

### Configuration

```typescript
interface ErrorServiceConfig {
  defaultDuration: number // Toast display duration (default: 6000ms)
  maxToasts: number // Max concurrent toasts (default: 1)
  maxQueueSize: number // Pending queue size (default: 20)
  dedupeWindowMs: number // Dedupe window (default: 2000ms)
}
```

### Key Methods

#### `handle(error: unknown): void`

Main entry point. Normalizes error, checks dedupe, shows toast.

```typescript
import { errorService } from '@/errors'

// Called automatically by global handlers
errorService.handle(error)
```

#### `fromUnknown(error: unknown): AppError`

Converts any error type to `AppError`. Handles:

- `AppError` instances (pass-through)
- `SubscriptionError` payloads (→ `WebSocketError`)
- Browser `WebSocket` error events (→ `NetworkError`)
- Standard `Error` objects (→ `NetworkError`)
- Strings, objects with `message` property
- Fallback for unknown types

### Deduplication

Errors with the same code within 2 seconds are suppressed:

```typescript
// First error → shows toast
throw new NetworkError('Connection failed') // ✅ Displayed

// Same error 500ms later → suppressed
throw new NetworkError('Connection failed') // ❌ Suppressed (same code)

// After 2s → shows again
throw new NetworkError('Connection failed') // ✅ Displayed
```

### Toast Queue

When `maxToasts` is reached, errors are queued and displayed sequentially:

```typescript
// maxToasts: 1 (default)
throw error1 // ✅ Displayed immediately
throw error2 // 📥 Queued
throw error3 // 📥 Queued

// When error1 toast closes → error2 displayed
// When error2 toast closes → error3 displayed
```

---

## Global Handler Integration

Global handlers are registered in `main.ts`:

```typescript
// main.ts
import { errorService } from '@/errors'

const app = createApp(App)

// Vue component errors (lifecycle, watchers, etc.)
app.config.errorHandler = (err) => {
  errorService.handle(err)
}

// Uncaught JavaScript errors
window.onerror = (_message, _source, _lineno, _colno, error) => {
  errorService.handle(error)
  return false // Allow default console logging
}

// Unhandled promise rejections
window.onunhandledrejection = (event) => {
  errorService.handle(event.reason)
}
```

---

## Usage Patterns

### Service Layer: Let Errors Propagate

Services do NOT wrap calls in try-catch:

```typescript
// ✅ CORRECT - Let errors propagate
class DatafeedService {
  async getBars(symbol: string, ...): Promise<Bar[]> {
    const response = await this.apiAdapter.getBars(symbol, ...)
    return response.data.bars
  }
}

// ❌ WRONG - Don't catch just to re-throw or log
class DatafeedService {
  async getBars(symbol: string, ...): Promise<Bar[]> {
    try {
      const response = await this.apiAdapter.getBars(symbol, ...)
      return response.data.bars
    } catch (error) {
      console.error('Error:', error)  // Unnecessary!
      throw error                      // Just re-throwing!
    }
  }
}
```

### When to Catch: Mitigation Examples

**Retry with backoff:**

```typescript
async fetchWithRetry(url: string, retries = 3): Promise<Response> {
  try {
    return await fetch(url)
  } catch (error) {
    if (retries > 0) {
      await sleep(1000)
      return this.fetchWithRetry(url, retries - 1)
    }
    throw error  // Exhausted retries → propagate
  }
}
```

**Fallback value:**

```typescript
async getConfig(): Promise<Config> {
  try {
    return await this.api.getConfig()
  } catch {
    return DEFAULT_CONFIG  // Use fallback
  }
}
```

**Partial results:**

```typescript
async getAllModulesHealth(): Promise<Map<string, ModuleHealth>> {
  const results = await Promise.allSettled(
    modules.map(m => this.getModuleHealth(m.name))
  )
  // Process partial results instead of all-or-nothing
  return new Map(results.map((r, i) => [
    modules[i].name,
    r.status === 'fulfilled' ? r.value : { error: r.reason }
  ]))
}
```

### WebSocket Error Handlers

For WebSocket subscriptions, provide `onError` callback for specific handling:

```typescript
await wsAdapter.orders.subscribe(
  'orders',
  { accountId: 'TEST' },
  (order) => handleOrder(order),
  (error) => {
    // Specific handling + throw to propagate to global handler
    throw WebSocketError.fromSubscription(error, { subscriptionName: 'Orders' })
  },
)
```

---

## Toast Notifications

### Component Setup

Toast container is mounted in `App.vue`:

```vue
<template>
  <AppToaster />
  <RouterView />
</template>
```

**Source:** [src/components/AppToaster.vue](../src/components/AppToaster.vue)

### Styling

Custom toast styles in `src/assets/toast.css`:

| Severity  | Class            | Color  |
| --------- | ---------------- | ------ |
| `error`   | `.toast-error`   | Red    |
| `warning` | `.toast-warning` | Orange |
| `info`    | `.toast-info`    | Blue   |

### Suppressed Toasts

Some error types don't show toasts:

| Error Type        | `showToast` | Reason                    |
| ----------------- | ----------- | ------------------------- |
| `AuthError`       | `false`     | Redirects to login        |
| `ValidationError` | `false`     | Displayed inline in forms |

---

## WebSocket Error Integration

WebSocket subscription errors integrate with the global error system via `WebSocketError.fromSubscription()`.

### Error Flow

```
Backend sends: { type: "{route}.error", payload: SubscriptionError }
                              │
                              ▼
WebSocketBase.routeErrorMessage()
                              │
      ┌───────────────────────┴───────────────────────┐
      ▼                                               ▼
Subscription has onError?                    No onError callback
      │                                               │
      ▼                                               ▼
onError(error) called                    globalErrorHandler(error)
      │                                               │
      ▼                                               ▼
throw WebSocketError.fromSubscription()   throw WebSocketError.fromSubscription()
      │                                               │
      └───────────────────────┬───────────────────────┘
                              ▼
                   window.onunhandledrejection
                              │
                              ▼
                   errorService.handle()
                              │
                              ▼
                        Toast displayed
```

**See:** [WEBSOCKET-ARCHITECTURE.md](./WEBSOCKET-ARCHITECTURE.md#subscription-error-handling) for complete WebSocket error handling details.

---

## Related Documentation

- [Backend Error Management](../../backend/docs/ERROR-MANAGEMENT.md) - Backend exception hierarchy (parallel structure)
- [WEBSOCKET-ARCHITECTURE.md](./WEBSOCKET-ARCHITECTURE.md) - WebSocket subscription error handling
- [src/services/README.md](../src/services/README.md) - Service layer patterns

---

**Version**: 1.0.0  
**Date**: December 19, 2025  
**Status**: ✅ Production Ready  
**Maintainers**: Development Team
