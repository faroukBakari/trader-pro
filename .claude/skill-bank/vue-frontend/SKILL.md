---
name: vue-frontend
description: Vue 3 Composition API + TypeScript patterns. Load when building components, composables, Pinia state, or reviewing Vue
keywords: [vue, composition-api, typescript, pinia, components]
category: frontend
disable-model-invocation: true
---

# Vue 3 Frontend Patterns

Standards and patterns for Vue 3 applications using Composition API, TypeScript, Pinia, and Vite — covering component design, state management, performance, data fetching, and testing.

---

## When to Use This Skill

- Building or reviewing Vue 3 Single File Components
- Designing composable functions for shared logic
- Structuring Pinia stores by domain
- Optimizing rendering performance
- Implementing forms with validation
- Setting up routing with guards and code splitting

---

## Methodology

### Phase 1: Component Design

**Always use `<script setup lang="ts">` syntax:**

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  title: string
  variant?: 'primary' | 'secondary'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
})

const emit = defineEmits<{
  close: []
  submit: [value: string]
}>()

const inputValue = ref('')
const isValid = computed(() => inputValue.value.length > 0)
</script>

<template>
  <div :class="['card', `card--${props.variant}`]">
    <h2>{{ title }}</h2>
    <slot />
  </div>
</template>

<style scoped>
.card { /* component styles */ }
</style>
```

**Component design rules:**
- One concern per component (single responsibility)
- PascalCase for component names, kebab-case for file names
- Use `withDefaults` + `defineProps<T>()` for typed props with defaults
- Use `defineEmits<T>()` with named tuple syntax for typed events
- Prefer slots and scoped slots over excessive props for layout composition

### Phase 2: Composables

Extract shared logic into `composables/` directory:

```typescript
// composables/useFetch.ts
import { ref, type Ref } from 'vue'

interface UseFetchReturn<T> {
  data: Ref<T | null>
  error: Ref<string | null>
  loading: Ref<boolean>
  execute: () => Promise<void>
}

export function useFetch<T>(url: string | Ref<string>): UseFetchReturn<T> {
  const data = ref<T | null>(null) as Ref<T | null>
  const error = ref<string | null>(null)
  const loading = ref(false)

  async function execute() {
    loading.value = true
    error.value = null
    try {
      const resolvedUrl = typeof url === 'string' ? url : url.value
      const response = await fetch(resolvedUrl)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      data.value = await response.json()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Unknown error'
    } finally {
      loading.value = false
    }
  }

  return { data, error, loading, execute }
}
```

**Composable rules:**
- Prefix with `use` (e.g., `useFetch`, `useAuth`, `useWebSocket`)
- Return typed refs and functions — never raw primitives
- Clean up side effects in `onUnmounted` or `watch` cleanup callbacks
- Use `watch` / `watchEffect` with precise dependency lists
- Use `provide` / `inject` sparingly for deep dependency injection

### Phase 3: State Management (Pinia)

Structure stores by domain, not by data shape:

```typescript
// stores/orders.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useOrderStore = defineStore('orders', () => {
  // State
  const orders = ref<Order[]>([])
  const loading = ref(false)

  // Getters (computed)
  const pendingOrders = computed(() =>
    orders.value.filter(o => o.status === 'pending')
  )
  const orderCount = computed(() => orders.value.length)

  // Actions
  async function fetchOrders() {
    loading.value = true
    try {
      orders.value = await orderApi.getAll()
    } finally {
      loading.value = false
    }
  }

  function addOrder(order: Order) {
    orders.value.push(order)
  }

  return { orders, loading, pendingOrders, orderCount, fetchOrders, addOrder }
})
```

**State management rules:**
- Use Setup Store syntax (function form) for better TypeScript inference
- `ref()` for simple state, `reactive()` only for complex nested objects
- `computed()` for all derived state — never derive in templates
- Actions for async logic — keep components thin
- Keep state normalized for collections (avoid deeply nested objects)

### Phase 4: Performance Optimization

| Technique | When to Use |
|-----------|-------------|
| `defineAsyncComponent` | Lazy-load heavy components not needed on initial render |
| `v-once` | Static content that never changes |
| `v-memo` | List items where re-render is expensive and deps are known |
| `shallowRef` / `shallowReactive` | Large objects where deep reactivity is unnecessary |
| `<Suspense>` | Async component loading with fallback UI |
| `computed` over `watch` | When derived value is sufficient (no side effects needed) |

**Lazy loading example:**
```typescript
import { defineAsyncComponent } from 'vue'

const HeavyChart = defineAsyncComponent(() =>
  import('./components/HeavyChart.vue')
)
```

**Avoid these performance traps:**
- ❌ Watchers that could be `computed` values
- ❌ `v-if` + `v-for` on the same element (use computed filtered list)
- ❌ Inline object/array props that create new references every render
- ❌ Missing `key` on `v-for` lists

### Phase 5: Routing

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('./views/HomeView.vue'),  // code splitting
    },
    {
      path: '/trading',
      component: () => import('./views/TradingView.vue'),
      meta: { requiresAuth: true },
    },
  ],
})

// Navigation guard
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !isAuthenticated()) {
    return { path: '/login' }
  }
})
```

**Routing rules:**
- Always use route-level code splitting via dynamic imports
- Use `meta` fields for route metadata (auth, breadcrumbs)
- Use `useRoute()` and `useRouter()` in `<script setup>` — never `this.$route`
- Navigation guards for auth, not component-level checks

### Phase 6: Forms & Validation

```vue
<script setup lang="ts">
import { ref } from 'vue'

const email = ref('')
const emailError = ref<string | null>(null)

function validateEmail() {
  if (!email.value) {
    emailError.value = 'Email is required'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value)) {
    emailError.value = 'Invalid email format'
  } else {
    emailError.value = null
  }
}

function handleSubmit() {
  validateEmail()
  if (emailError.value) return
  // submit logic
}
</script>

<template>
  <form @submit.prevent="handleSubmit" novalidate>
    <label for="email">Email</label>
    <input
      id="email"
      v-model="email"
      type="email"
      autocomplete="email"
      :aria-invalid="!!emailError"
      :aria-describedby="emailError ? 'email-error' : undefined"
      @blur="validateEmail"
    />
    <p v-if="emailError" id="email-error" role="alert">
      {{ emailError }}
    </p>
    <button type="submit">Submit</button>
  </form>
</template>
```

**Form rules:**
- Validate on blur with debouncing for performance
- Use `v-model` for controlled bindings
- Associate labels, errors, and hints with proper `for` / `aria-describedby`
- Handle loading, error, and success states explicitly

### Phase 7: Error Handling

```typescript
// Global error handler (main.ts)
app.config.errorHandler = (err, instance, info) => {
  console.error('Vue error:', err, info)
  // report to error tracking service
}
```

**Component-level:**
- Use `onErrorCaptured` for local error boundaries
- Wrap async operations in `try/catch` with user-friendly messages
- Display fallback UI for error states — never blank screens

---

## TypeScript Integration Rules

- Enable `strict: true` in `tsconfig.json`
- Use `defineProps<T>()` — never `defineProps({})` with runtime validation
- Type all refs: `ref<string>('')`, `ref<Order | null>(null)`
- Type emits with named tuples: `defineEmits<{ update: [value: string] }>()`
- Use `type` imports for interfaces: `import type { Order } from '@/types'`
- Generic composables when return type varies: `useFetch<T>(url)`

---

## Styling Rules

- Use `<style scoped>` for component styles — prevents leakage
- CSS custom properties (variables) for theming and design tokens
- Mobile-first responsive design with CSS Grid and Flexbox
- BEM or flat class naming — avoid deep nesting (> 3 levels)
- Ensure focus states and sufficient color contrast

---

## Anti-Patterns

- ❌ **Options API in new code** — Always use Composition API with `<script setup>`
- ❌ **`v-html` without sanitization** — XSS vector; sanitize rigorously or avoid
- ❌ **Mutating props** — Props are read-only; emit events to parent instead
- ❌ **`this.$refs` in setup** — Use template refs with `ref<HTMLElement | null>(null)`
- ❌ **Store abuse** — Not everything belongs in Pinia; prefer local state for component-scoped data
- ❌ **Watchers for derived state** — Use `computed` when no side effects are needed
- ✅ **Thin components, fat composables** — Components orchestrate; composables contain logic
