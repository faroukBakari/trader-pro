---
name: frontend-testing
description: Vitest/Vue 3 frontend testing patterns for the trader-pro architecture. Use when writing frontend tests, selecting test patterns, mocking services/WebSockets, or analyzing frontend coverage. Complements test-strategy skill with Vitest-specific patterns.
---

# Frontend Testing

Vitest and Vue 3-specific testing methodology for the trader-pro frontend. Covers component testing, service auto-detection, WebSocket mocking, and project conventions. Apply `test-strategy` skill first for general methodology, then this skill for Vitest/Vue patterns.

---

## When to Use This Skill

- Writing frontend tests (components, services, plugins, composables, stores)
- Selecting the right test pattern for a Vue 3 target
- Mocking WebSockets, services, or Pinia stores
- Analyzing frontend test coverage gaps
- Debugging Vitest test failures

---

## Test Organization

```
frontend/src/
├── components/__tests__/     # Component tests
│   └── {Component}.spec.ts
├── services/__tests__/       # Service tests (highest value)
│   └── {service}.spec.ts
├── plugins/__tests__/        # Plugin/WebSocket tests
│   └── {plugin}.spec.ts
└── stores/__tests__/         # Pinia store tests
    └── {store}.spec.ts
```

**Priority**: Service & plugin tests > component tests (higher signal-to-noise).

---

## Pattern Selection

| Target | Pattern | Setup |
|--------|---------|-------|
| Service class | Auto-detection `new Service(true)` | No `vi.mock()` needed |
| Vue component | `mount(Component)` | `@vue/test-utils` |
| WebSocket | `vi.stubGlobal('WebSocket', Mock)` | Custom MockWebSocket class |
| Pinia store | `setActivePinia(createPinia())` | In `beforeEach` |
| Plugin/composable | Direct import + isolated call | No special setup |

---

## Common Patterns

### Service Auto-Detection (preferred)

```typescript
const service = new ApiService(true) // Auto-detects test env via process.env.VITEST
const result = await service.getHealthStatus()
expect(result.status).toBe('ok')
```

Avoid `vi.mock()` when the service supports mock mode via constructor.

### Component Mounting

```typescript
import { mount } from '@vue/test-utils'
import MyComponent from '../MyComponent.vue'

const wrapper = mount(MyComponent)
expect(wrapper.find('header').exists()).toBe(true)
await wrapper.vm.$nextTick()
```

### WebSocket Mocking

```typescript
class MockWebSocket {
  static CONNECTING = 0; static OPEN = 1; static CLOSING = 2; static CLOSED = 3
  readyState = MockWebSocket.CONNECTING
  simulateOpen() {
    this.readyState = MockWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }
  simulateMessage(data: object) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent)
  }
}
beforeEach(() => {
  vi.stubGlobal('WebSocket', vi.fn(() => new MockWebSocket()))
})
```

### Pinia Store

```typescript
import { setActivePinia, createPinia } from 'pinia'
beforeEach(() => { setActivePinia(createPinia()) })
```

---

## Conventions

- **File naming**: `{Name}.spec.ts` (NOT `.test.ts`)
- **Structure**: `describe('{ComponentOrService}')` → `beforeEach()` → `it('behavior')`
- **Test names**: `it('shows loading state when data is pending')`
- **Focus**: One behavior per `it()` block
- **Output**: Test rendered output and user interactions, not internal component state
- **Generated clients**: Files in `clients_generated/` are excluded — don't mock them, they're tested via backend contracts

### Client Generation Awareness

Frontend tests auto-generate clients from backend specs before running. The `make -C frontend test` target handles this automatically. Never run raw `npm run test:unit`.

---

## Make Targets

```bash
make -C frontend test          # Run tests once (--bail=1, auto-generates clients)
make -C frontend test-backend  # Run tests with real backend (not mock)
make -C frontend lint          # Lint (auto-generates clients first)
make -C frontend type-check    # TypeScript check (auto-generates clients first)
```

---

## Key Files

| Purpose | Location |
|---------|----------|
| Test setup & client validation | `frontend/src/test-setup.ts` |
| Vitest config | `frontend/vitest.config.ts` |
| Service test README | `frontend/src/services/__tests__/README.md` |

---

## Anti-Patterns

- ❌ Using `vi.mock()` when service supports auto-detection — prefer constructor pattern
- ❌ Using `.test.ts` extension — project standard is `.spec.ts`
- ❌ Testing internal component state — test rendered output and events instead
- ❌ Running `npm run test:unit` directly — use `make -C frontend test`
- ✅ Read sibling `*.spec.ts` files first to match existing patterns
