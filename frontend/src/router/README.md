# Router Authentication

**Last Updated:** November 14, 2025  
**Status:** ✅ Production Ready

Stateless authentication guards for Vue Router with API introspection and automatic token refresh.

---

## Overview

The router implements authentication guards that:

- ✅ Validate authentication before navigation
- ✅ Use direct API introspection (no Pinia store dependency)
- ✅ Cache validation results (30-second TTL) to minimize API calls
- ✅ Preserve redirect URLs for post-login navigation
- ✅ Automatically refresh expired tokens
- ✅ Monitor auth status periodically on protected routes
- ✅ Handle WebSocket cleanup on logout

---

## Architecture

```
Router Guards (beforeEach)
    ↓
AuthService.checkAuthStatus()
    ↓
ApiAdapter.introspectToken()
    ↓
GET /api/v1/auth/introspect
    ↓
Backend Validates Cookie
```

### Key Design Decisions

**1. Stateless Guards**

- No Pinia store imports
- Direct API validation via `authService.checkAuthStatus()`
- No local authentication state

**2. API Introspection**

- Lightweight `/introspect` endpoint
- Returns token status: `valid` | `expired` | `error`
- 30-second cache in `ApiAdapter` to reduce API calls

**3. Auto Token Refresh**

- If access token expired, attempts silent refresh
- Uses refresh token from localStorage
- Updates cookie automatically on success

**4. Redirect Preservation**

- Stores intended destination in query param
- Navigates to original URL after login

---

## Routes Configuration

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/chart',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: {
        requiresAuth: false, // Public route
      },
    },
    {
      path: '/chart',
      name: 'trader-chart',
      component: () => import('../views/TraderChartView.vue'),
      meta: {
        requiresAuth: true, // Protected route
      },
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../views/NotFoundView.vue'),
    },
  ],
})
```

### Route Meta Fields

- `requiresAuth: true` - Route requires authentication
- `requiresAuth: false` - Public route (no authentication needed)
- No meta field - Defaults to public

---

## Authentication Guard

### Implementation

```typescript
import { useAuthService } from '@/services/authService'

const authService = useAuthService()

router.beforeEach(async (to, _, next) => {
  // Check if route requires authentication
  if (to.meta.requiresAuth) {
    // Validate authentication status
    const isAuthenticated = await authService.checkAuthStatus()

    if (isAuthenticated) {
      // Start periodic auth monitoring
      startAuthMonitoring()
      return next()
    }

    // Not authenticated - redirect to login
    return to.name !== 'login'
      ? next({
          name: 'login',
          query: { redirect: to.fullPath },
        })
      : next()
  }

  // Public route or already at login
  if (to.name === 'login') {
    const isAuthenticated = await authService.checkAuthStatus()

    // Already authenticated - redirect to chart
    if (isAuthenticated) {
      return next({ name: 'trader-chart' })
    }
  }

  return next()
})
```

### Guard Flow

1. **Check Route Meta**: If `requiresAuth: true`, validate authentication
2. **Call AuthService**: `checkAuthStatus()` introspects token and auto-refreshes if needed
3. **Success**: Allow navigation and start auth monitoring
4. **Failure**: Redirect to login with return URL
5. **Login Page**: If already authenticated, redirect to chart

---

## Auth Status Monitoring

### Purpose

Periodically check authentication status on protected routes to detect token expiration and logout automatically.

### Implementation

```typescript
let authMonitorTimeout: NodeJS.Timeout | null = null

async function watchAuthStatus() {
  // Only monitor on protected routes
  if (router.currentRoute.value.meta.requiresAuth) {
    const isValid = await authService.checkAuthStatus()

    if (!isValid) {
      console.log('Token expired - disconnecting WebSockets and redirecting')

      // Cleanup WebSocket connections
      WebSocketBase.logout()

      // Redirect to login
      router.push({
        name: 'login',
        query: { redirect: router.currentRoute.value.fullPath },
      })
    } else {
      // Schedule next check in 10 seconds
      authMonitorTimeout = setTimeout(watchAuthStatus, 10 * 1000)
    }
  }
}

// Start monitoring after successful navigation
router.beforeEach(async (to, _, next) => {
  // Clear existing monitor
  if (authMonitorTimeout) {
    clearTimeout(authMonitorTimeout)
    authMonitorTimeout = null
  }

  // ... authentication checks ...

  if (to.meta.requiresAuth && isAuthenticated) {
    // Start monitoring 10 seconds after navigation
    authMonitorTimeout = setTimeout(watchAuthStatus, 10 * 1000)
  }

  return next()
})
```

### Monitoring Features

✅ **Periodic Checks**: Validates auth every 10 seconds on protected routes  
✅ **Auto Logout**: Redirects to login if token expired  
✅ **WebSocket Cleanup**: Disconnects all WebSocket connections on logout  
✅ **Redirect Preservation**: Saves current route for post-login return  
✅ **Efficient**: Runs only on protected routes

---

## Redirect Handling

### Login Redirect

When redirecting to login, the target route is preserved:

```typescript
// User tries to access /chart without authentication
router.push('/chart')

// Router redirects to login with query param
// URL: /login?redirect=/chart

// After successful login, navigate back
const redirect = (route.query.redirect as string) || '/chart'
router.push(redirect)
```

### Implementation in LoginView

```typescript
<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthService } from '@/services/authService'

const route = useRoute()
const router = useRouter()
const authService = useAuthService()

async function handleGoogleSignIn(response: CredentialResponse) {
  await authService.loginWithGoogleToken(response.credential!)

  // Navigate to intended destination
  const redirect = (route.query.redirect as string) || '/chart'
  router.push(redirect)
}
</script>
```

---

## API Introspection

### Endpoint

`GET /api/v1/auth/introspect`

Validates access token from cookie and returns status.

### Response

```typescript
interface TokenIntrospectResponse {
  status: 'valid' | 'expired' | 'error'
  exp: number | null // Token expiration timestamp
  error: string | null // Error message if status is 'error'
}
```

### Example

```typescript
import { ApiAdapter } from '@/plugins/apiAdapter'

const result = await ApiAdapter.getInstance().introspectToken()

if (result.data.status === 'valid') {
  console.log('Token expires at:', new Date(result.data.exp! * 1000))
} else if (result.data.status === 'expired') {
  console.log('Token expired, attempting refresh...')
} else {
  console.error('Token error:', result.data.error)
}
```

### Caching Strategy

**ApiAdapter** caches introspection results for 30 seconds:

```typescript
class ApiAdapter {
  private introspectCache: {
    result: TokenIntrospectResponse | null
    timestamp: number
  } = { result: null, timestamp: 0 }

  async introspectToken() {
    const now = Date.now()
    const cacheValid = now - this.introspectCache.timestamp < 30 * 1000

    if (cacheValid && this.introspectCache.result) {
      return { data: this.introspectCache.result }
    }

    // Call API
    const result = await this.authApi.introspect()

    // Update cache
    this.introspectCache = {
      result: result.data,
      timestamp: now,
    }

    return result
  }
}
```

**Benefits:**

- ✅ Reduces API calls (max 1 per 30 seconds)
- ✅ Faster navigation (cached validation)
- ✅ Lower backend load

---

## WebSocket Cleanup

### Integration with WebSocketBase

When user logs out or token expires, all WebSocket connections must be closed:

```typescript
import { WebSocketBase } from '@/plugins/wsClientBase'

// On logout or token expiry
WebSocketBase.logout()
```

### What `logout()` Does

1. Disconnects WebSocket connection
2. Clears all subscriptions
3. Resets internal state
4. Prevents reconnection attempts

### Automatic Cleanup

The router guard automatically calls `WebSocketBase.logout()` when:

- Token expires during monitoring
- User manually logs out

---

## Security Considerations

### Strengths

✅ **Stateless Guards**: No local auth state to desync  
✅ **Server-Side Validation**: Every navigation verified with backend  
✅ **Short Cache TTL**: 30-second cache minimizes stale state  
✅ **Auto Refresh**: Expired tokens refreshed automatically  
✅ **WebSocket Cleanup**: Prevents unauthorized connections  
✅ **Redirect Preservation**: Smooth UX after login

### Attack Mitigation

**CSRF Protection:**

- Cookies have `SameSite=Strict` flag
- Router guards validate cookie presence

**XSS Protection:**

- Access tokens in HttpOnly cookies (JavaScript cannot access)
- No token storage in localStorage

**Session Hijacking:**

- Device fingerprinting validates requests
- Refresh token rotation prevents reuse

---

## Testing

### Unit Tests

**Router Guard Tests:**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import router from '../index'
import { useAuthService } from '@/services/authService'

vi.mock('@/services/authService')

describe('Router Guards', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('allows navigation to public routes without authentication', async () => {
    const authService = useAuthService()
    vi.mocked(authService.checkAuthStatus).mockResolvedValue(false)

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('login')
  })

  it('blocks navigation to protected routes when not authenticated', async () => {
    const authService = useAuthService()
    vi.mocked(authService.checkAuthStatus).mockResolvedValue(false)

    await router.push('/chart')

    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/chart')
  })

  it('allows navigation to protected routes when authenticated', async () => {
    const authService = useAuthService()
    vi.mocked(authService.checkAuthStatus).mockResolvedValue(true)

    await router.push('/chart')

    expect(router.currentRoute.value.name).toBe('trader-chart')
  })

  it('redirects authenticated users from login page', async () => {
    const authService = useAuthService()
    vi.mocked(authService.checkAuthStatus).mockResolvedValue(true)

    await router.push('/login')

    expect(router.currentRoute.value.name).toBe('trader-chart')
  })
})
```

### Integration Tests

**Full Authentication Flow:**

```typescript
describe('Router Authentication Integration', () => {
  it('preserves redirect after login', async () => {
    // Try to access protected route without auth
    await router.push('/chart')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/chart')

    // Simulate login
    await authService.loginWithGoogleToken('mock-token')

    // Navigate using redirect
    const redirect = router.currentRoute.value.query.redirect as string
    await router.push(redirect)

    expect(router.currentRoute.value.name).toBe('trader-chart')
  })
})
```

---

## Common Patterns

### Adding New Protected Route

```typescript
{
  path: '/portfolio',
  name: 'portfolio',
  component: () => import('../views/PortfolioView.vue'),
  meta: {
    requiresAuth: true,  // Add this to protect route
  },
}
```

### Adding Public Route

```typescript
{
  path: '/about',
  name: 'about',
  component: () => import('../views/AboutView.vue'),
  meta: {
    requiresAuth: false,  // Explicitly mark as public
  },
}
```

### Custom Guard Logic

```typescript
router.beforeEach(async (to, from, next) => {
  // Standard auth check
  if (to.meta.requiresAuth) {
    const isAuthenticated = await authService.checkAuthStatus()
    if (!isAuthenticated) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }
  }

  // Custom logic (e.g., role-based access)
  if (to.meta.requiresAdmin) {
    const user = await authService.getCurrentUser()
    if (!user.isAdmin) {
      return next({ name: 'forbidden' })
    }
  }

  return next()
})
```

---

## Troubleshooting

### Issue: Infinite redirect loop

**Symptoms:** `/login` → `/chart` → `/login` → ...

**Causes:**

- `checkAuthStatus()` returning wrong value
- Cache issues with introspection

**Solutions:**

1. Check browser DevTools → Application → Cookies for `access_token`
2. Clear introspection cache: restart frontend
3. Check backend `/introspect` endpoint response

### Issue: "Token expired" immediately after login

**Symptoms:** Login succeeds but immediately redirects to login

**Causes:**

- Clock skew between frontend and backend
- Token expiry set too short

**Solutions:**

1. Check system clocks (frontend and backend servers)
2. Verify `ACCESS_TOKEN_EXPIRE_MINUTES=5` in backend config
3. Check backend JWT signing (ensure `exp` field set correctly)

### Issue: Auth monitoring not working

**Symptoms:** Token expires but no automatic logout

**Causes:**

- Monitor timeout cleared prematurely
- Monitor not started after navigation

**Solutions:**

1. Check `authMonitorTimeout` is set after navigation
2. Verify `watchAuthStatus()` function runs periodically
3. Add console logs to debug monitor lifecycle

---

## Related Documentation

- [Auth Service](../services/README.md#authservice) - Authentication service implementation
- [Auth Module](../../../backend/src/trading_api/modules/auth/README.md) - Backend authentication
- [Authentication Guide](../../../docs/AUTHENTICATION.md) - Comprehensive cross-cutting guide
- [WebSocket Architecture](../../docs/WEBSOCKET-ARCHITECTURE.md) - WebSocket cleanup integration

---

**Last Updated:** November 14, 2025  
**Maintained by:** Development Team
