# TradingView Bundle Maintenance Guide

**Version**: 1.0.0  
**Last Updated**: January 13, 2026  
**Status**: ✅ Active Guide

---

## Table of Contents

1. [Overview](#overview)
2. [Bundle Architecture](#bundle-architecture)
3. [Debugging Methodology](#debugging-methodology)
4. [Case Study 1: Position Bracket Pre-Population Bug](#case-study-1-position-bracket-pre-population-bug)
5. [Case Study 2: Position Dialog Field Sync Bug](#case-study-2-position-dialog-field-sync-bug)
6. [RxJS Patterns in TradingView Bundles](#rxjs-patterns-in-tradingview-bundles)
7. [Common TradingView Bundle Issues](#common-tradingview-bundle-issues)
8. [Maintenance Best Practices](#maintenance-best-practices)
9. [Reference: Key Classes](#reference-key-classes)
10. [Appendix: Tick Value Calculation](#appendix-tick-value-calculation)

---

## Overview

### Purpose

This guide documents the **maintenance patterns, debugging strategies, and known solutions** for TradingView Trading Terminal bundle modifications. The TradingView library is distributed as minified/obfuscated JavaScript bundles, making debugging and customization challenging.

**Target Audience**: Developers maintaining the broker integration who need to:

- Debug TradingView dialog issues
- Understand obfuscated class structures
- Modify bundle behavior
- Investigate field synchronization problems
- Work with RxJS observable patterns

### Key Concepts

- **Bundles**: Pre-compiled JavaScript files from TradingView (`order-view-controller.js`, `trading.js`, `trading-account-manager.js`)
- **Obfuscation**: Class names (e.g., `Pt`, `bt`, `ie`) and parameters are minified
- **Unobfuscation**: Process of adding readable comments/rewrites to understand minified code
- **Preservation**: Never delete original code; add readable versions alongside

---

## Bundle Architecture

### Bundle Files Overview

```
frontend/public/trading_terminal/bundles/
├── order-view-controller.4f3dc6de299e33f3954b.js  # Order/Position dialog logic
├── trading.ebdd16d99f1b0686abf5.js                # Core trading operations
├── trading-account-manager.f46b5e4741c5dccc2102.js # Account Manager UI
└── ... (other bundles)
```

### Key Bundle Responsibilities

| Bundle                         | Purpose                             | Key Classes                                                          |
| ------------------------------ | ----------------------------------- | -------------------------------------------------------------------- |
| **order-view-controller.js**   | Dialog view models (Order/Position) | `Pt` (PositionViewModel), `bt` (OrderViewModel), `ie` (BracketModel) |
| **trading.js**                 | Trading operations, calculations    | `calculatePipValue()`, trading utilities                             |
| **trading-account-manager.js** | Account Manager UI components       | Account panel, position list, order list                             |

### Obfuscation Patterns

**Before Unobfuscation:**

```javascript
class Pt {
  constructor(e, t, n, r, i, o, s, a, l, c) {
    // 10 cryptic parameters
  }
}
```

**After Unobfuscation (Comment or Rewrite):**

```javascript
class Pt {
  // PositionViewModel
  constructor(
    adapter, // e - IBrokerConnectionAdapterHost
    position, // t - Position object
    brackets, // n - Brackets {stopLoss?, takeProfit?}
    settings$, // r - Observable<Settings>
    account$, // i - Observable<Account>
    subscribeEquity, // o - Function to subscribe to equity updates
    subscribeRealtime, // s - Function to subscribe to realtime quotes
    instrumentInfo, // a - InstrumentInfo for symbol
    leverageInfo$, // l - Observable<LeverageInfo>
    formatter, // c - Price formatter
  ) {
    // Original code preserved exactly
  }
}
```

**Naming Conventions:**

- Classes: Single/double uppercase letters (`Pt`, `bt`, `ie`, `gt`)
- Methods: Camelcase with underscores (`_createModels`, `_subscribe`)
- Observables: End with `$` (`_equity$`, `_quotes$`, `_pipValues$`)

---

## Debugging Methodology

### Step-by-Step Unobfuscation Approach

#### 1. Identify the Obfuscated Class

Search for class declarations in bundle files:

```bash
grep -n "class Pt " order-view-controller.*.js
# Result: line 5333: class Pt {
```

#### 2. Map Parameters by Usage Analysis

Trace how parameters are used within the class:

```javascript
// Example: Analyzing Pt constructor
constructor(e, t, n, r, i, o, s, a, l, c) {
  this._adapter = e        // Used with Trading Host methods → adapter
  this._position = t       // Has .id, .qty, .avgPrice → position
  this._brackets = n       // Has .stopLoss, .takeProfit → brackets
  // ... continue pattern analysis
}
```

**Analysis Techniques:**

- Look for method calls (e.g., `e.getHost()` → Trading Host adapter)
- Check property access (e.g., `t.id`, `t.qty` → Position interface)
- Identify RxJS patterns (`pipe`, `subscribe` → Observable)
- Cross-reference with TradingView type definitions

#### 3. Rewrite with Readable Names

**Option A: Inline Comments**

```javascript
constructor(
  e, // adapter: IBrokerConnectionAdapterHost
  t, // position: Position
  n, // brackets: Brackets
  // ...
) { /* original code */ }
```

**Option B: Separate Documentation** (this guide)

**Option C: Side-by-Side Rewrite** (for complex logic)

```javascript
// Original minified code (PRESERVED):
this._equity$ = T(fromEventPattern(o))

// Readable equivalent (COMMENTED):
// this._equity$ = shareObservable(
//   fromEventPattern(subscribeEquity)
// );
```

### Console Logging Strategy

#### When to Add Logs

- **Constructor calls**: Verify parameters and initialization
- **Observable emissions**: Track data flow in RxJS chains
- **Subscription handlers**: Debug sync mechanisms
- **Error conditions**: Capture failure paths

#### Logging Best Practices

```javascript
// ✅ GOOD: Contextual, structured logs
console.log('[ie.subscribe] combineLatest emitted:', {
  enabled: values.enabled,
  parentPrice: values.parentPrice,
  pipValue: values.pipValue,
  equity: values.equity,
})

// ❌ BAD: Generic, unhelpful logs
console.log('value:', values)
```

#### Cleanup After Debugging

**Never delete logs** - comment them out for future reference:

```javascript
// console.log('[Pt.constructor] Position:', position);
// console.log('[Pt._subscribe] Setting up combineLatest');
```

**Rationale**: Future maintainers can quickly re-enable logs without guessing what to log.

---

## Case Study 1: Position Bracket Pre-Population Bug

### Problem Description

**Issue**: When clicking the **edit button** on a position in TradingView's **Account Manager**, the position editing dialog opens with **empty Take Profit and Stop Loss fields**, even though bracket orders exist on the position.

**User Impact**: Users must manually re-enter TP/SL values every time they want to modify position brackets.

**Observed Behavior**:

```
1. User has open position with TP=$175.00, SL=$165.00
2. User clicks "Edit" button in Account Manager
3. Position dialog opens with:
   - Quantity: ✅ Pre-filled (100)
   - Price: ✅ Pre-filled ($170.50)
   - Take Profit: ❌ Empty
   - Stop Loss: ❌ Empty
```

### Root Cause Analysis

#### Investigation Path

**Step 1: Trace the Call Chain**

```
User clicks "Edit" in Account Manager
  ↓
trading-account-manager.js
  → Calls Trading Host method
  ↓
trading.js
  → Routes to customUI.showPositionDialog hook (if provided)
  ↓
TraderChartContainer.vue (our code)
  → Receives position and brackets parameters
```

**Step 2: Inspect Parameters at Hook**

```typescript
customUI: {
  showPositionDialog: async (position, brackets, focus) => {
    console.log('Position:', position)
    // Output: { id: 'POS-123', qty: 100, avgPrice: 170.50, ... }

    console.log('Brackets:', brackets)
    // Output: {} ❌ EMPTY OBJECT
  }
}
```

**Step 3: Compare with TradingView Type Definitions**

```typescript
// Position interface (from TradingView types)
interface Position {
  id: string
  qty: number
  avgPrice: number
  side: Side
  // ❌ NO stopLoss or takeProfit fields
}

// Order interface (from TradingView types)
interface Order {
  id: string
  parentId?: string // Links to position
  parentType?: ParentType // 2 = ParentType.Position
  stopPrice?: number // Stop Loss bracket
  limitPrice?: number // Take Profit bracket
}
```

#### Root Cause: Architecture Mismatch

**Finding**: TradingView's `Position` interface **does not contain bracket fields**. Bracket orders are stored as **separate `Order` records** with:

- `parentId`: Links to the position ID
- `parentType`: Set to `ParentType.Position` (enum value 2)
- `stopPrice`: Contains Stop Loss price
- `limitPrice`: Contains Take Profit price

**Why It Fails**: The `customUI.showPositionDialog` hook receives an **empty brackets object `{}`** because TradingView doesn't automatically fetch bracket orders when opening the dialog from the Account Manager.

**Diagram: Data Relationships**

```
Position Record                Bracket Order Records
┌──────────────────┐          ┌──────────────────────────┐
│ id: 'POS-123'    │◄─────────│ id: 'ORD-456'            │
│ qty: 100         │ parentId │ parentId: 'POS-123'      │
│ avgPrice: 170.50 │          │ parentType: 2 (Position) │
│ side: 1 (Buy)    │          │ stopPrice: 165.00 ⬅ SL   │
└──────────────────┘          └──────────────────────────┘
                              ┌──────────────────────────┐
                              │ id: 'ORD-789'            │
                              │ parentId: 'POS-123'      │
                              │ parentType: 2 (Position) │
                              │ limitPrice: 175.00 ⬅ TP  │
                              └──────────────────────────┘
```

### Solution Implementation

#### Approach: Enrich Brackets in Custom Hook

Since TradingView doesn't fetch bracket orders automatically, we **fetch them manually** in the `customUI.showPositionDialog` hook and enrich the `brackets` parameter before passing it to the dialog.

#### Implementation Details

**File**: `frontend/src/components/TraderChartContainer.vue` (lines 217-252)

**Code**:

```typescript
customUI: {
  showPositionDialog: async (
    position: Position | IndividualPosition,
    brackets: Brackets,
    focus?: OrderTicketFocusControl,
  ): Promise<boolean> => {
    // If brackets are empty, fetch bracket orders for this position
    let enrichedBrackets = brackets
    try {
      // Step 1: Fetch all orders from backend
      const orders: Order[] = await brokerService!.orders()

      // Step 2: Filter for bracket orders linked to this position
      const bracketOrders = orders.filter(
        (o) =>
          'parentId' in o &&
          o.parentId === position.id &&
          o.parentType === ParentType.Position, // enum value 2
      )

      // Step 3: Extract Stop Loss and Take Profit from bracket orders
      const stopLossOrder = bracketOrders.find((o) => o.stopPrice !== undefined)
      const takeProfitOrder = bracketOrders.find(
        (o) => o.limitPrice !== undefined && o.stopPrice === undefined,
      )

      // Step 4: Create enriched brackets object
      enrichedBrackets = {
        stopLoss: stopLossOrder?.stopPrice,
        takeProfit: takeProfitOrder?.limitPrice,
      }

      console.log(
        `[customUI.showPositionDialog] Enriched brackets for position ${position.id}:`,
        enrichedBrackets,
      )
    } catch (e) {
      console.warn(`[customUI.showPositionDialog] Failed to fetch bracket orders:`, e)
    }

    // Step 5: Call original showPositionBracketsDialog with enriched data
    return brokerService!.showPositionBracketsDialog(position, enrichedBrackets, focus)
  },
},
```

**Key Points**:

1. **Async Hook**: Made hook `async` to fetch orders from backend
2. **Filter Logic**: Uses `parentId === position.id` AND `parentType === ParentType.Position`
3. **Stop Loss vs Take Profit**:
   - Stop Loss: Has `stopPrice` field
   - Take Profit: Has `limitPrice` field **without** `stopPrice`
4. **Graceful Failure**: Wraps fetch in try/catch, falls back to original empty brackets on error

#### Alternative Approaches Considered

**Option 1: Modify Backend Position Response** ❌

- Would require adding `stopLoss`/`takeProfit` to Position model
- Violates single responsibility (Position shouldn't contain Orders)
- Breaks separation of concerns

**Option 2: Cache Bracket Orders in Frontend State** ❌

- Adds complexity for single-use case
- Stale data risk
- Over-engineering for simple problem

**Option 3: Fetch in Hook (Selected)** ✅

- Simple, localized solution
- No backend changes required
- Always fetches fresh data
- Minimal performance impact (single API call on dialog open)

### Validation

**Test Case**: Position with existing TP/SL brackets

1. Open position with TP=$175.00, SL=$165.00
2. Click "Edit" in Account Manager
3. **Expected**: Dialog pre-fills TP=$175.00, SL=$165.00
4. **Result**: ✅ Brackets correctly pre-populated

**User Confirmation**: January 13, 2026 - User confirmed brackets now pre-populate correctly.

---

## Case Study 2: Position Dialog Field Sync Bug

### Problem Description

**Issue**: In the position edit dialog, **fields don't sync automatically**. When changing the **Price** field (e.g., from $165.00 to $170.00), the **Ticks** and **$\*\* fields remain static instead of recalculating.

**User Impact**: Users see incorrect risk calculations unless they manually click other fields to trigger sync.

**Observed Behavior**:

```
Position Dialog (BROKEN):
1. Set Stop Loss Price = $165.00
   → Ticks = 0.00 (doesn't update)
   → $ = $0.00 (doesn't update)
2. Click in Ticks field
   → NOW Ticks = -5.00 (delayed sync)
   → $ = -$5.00 (delayed sync)

Order Dialog (WORKING):
1. Set Stop Loss Price = $165.00
   → Ticks = -5.00 ✅ (instant sync)
   → $ = -$5.00 ✅ (instant sync)
```

### Root Cause Analysis

#### Investigation Path

**Step 1: Unobfuscate Position Dialog Class**

Located `class Pt` (PositionViewModel) in `order-view-controller.js` line 5333:

```javascript
// Unobfuscated constructor signature:
class Pt {
  // PositionViewModel
  constructor(
    adapter, // IBrokerConnectionAdapterHost
    position, // Position object
    brackets, // Brackets {stopLoss?, takeProfit?}
    settings$, // Observable<Settings>
    account$, // Observable<Account>
    subscribeEquity, // Function: subscribe to equity updates
    subscribeRealtime, // Function: subscribe to realtime quotes
    instrumentInfo, // InstrumentInfo for symbol
    leverageInfo$, // Observable<LeverageInfo>
    formatter, // Price formatter
  ) {
    /* ... */
  }
}
```

**Step 2: Analyze Sync Mechanism**

The field sync is handled by `ie` class (BracketModel) which uses **RxJS `combineLatest`**:

```javascript
// ie.subscribe method (BracketModel sync logic)
combineLatest({
  enabled: this._enabled$,
  parentPrice: this._parentPrice$, // ⬅ Depends on _equity$ and _quotes$
  sideSign: this._sideSign$,
  pipValue: this._pipValue$,
  equity: this._equity$, // ❌ Never emits initially
  amount: this._amount$,
  bracketValuesWithFocusedControl: this._bracketValuesWithFocusedControl$,
}).subscribe(this._handleBracketsValuesChange) // ⬅ Sync handler NEVER fires
```

**Step 3: Trace Observable Dependencies**

```
_handleBracketsValuesChange (sync handler)
  ↑ triggered by
combineLatest({ ..., equity: _equity$, ... })
  ↑ depends on
_equity$ (equity observable)
  ↑ created from
fromEventPattern(subscribeEquity) ❌ NO startWith
```

**Step 4: Compare with Working Order Dialog**

```javascript
// Order dialog (bt class) - WORKS ✅
this._equity$ = fromEventPattern(subscribeEquity).pipe(
  startWith(NaN), // ⬅ Emits immediately on subscription
  share({ connector: () => new ReplaySubject(1) }),
)

// Position dialog (Pt class) - BROKEN ❌
this._equity$ = T(
  // T = shareObservable helper
  fromEventPattern(subscribeEquity), // ⬅ Only emits when event fires
)
```

#### Root Cause: Missing `startWith()` Operators

**Finding**: The Position dialog's `_equity$` and `_quotes$` observables are created with `fromEventPattern()` **without** `startWith()` operators, causing them to **never emit an initial value**.

**Why It Breaks `combineLatest`**:

```javascript
// RxJS combineLatest behavior:
combineLatest([obs1$, obs2$, obs3$]).subscribe(...)
// ⬆ Only fires AFTER ALL observables have emitted at least once
```

If `_equity$` never emits (waiting for equity update event), `combineLatest` **never fires**, and the sync handler `_handleBracketsValuesChange` **never executes**.

**Diagram: Observable Flow**

```
Position Dialog (BROKEN):
┌────────────────────┐
│ subscribeEquity    │ (event stream)
└────────┬───────────┘
         ↓ fromEventPattern
┌────────────────────┐
│ _equity$           │ ❌ No initial emission
└────────┬───────────┘
         ↓ combineLatest waits...
┌────────────────────┐
│ combineLatest      │ ⏸ BLOCKED (never emits)
└────────┬───────────┘
         ↓
┌────────────────────┐
│ subscribe callback │ ❌ Never called
└────────────────────┘

Order Dialog (WORKING):
┌────────────────────┐
│ subscribeEquity    │ (event stream)
└────────┬───────────┘
         ↓ fromEventPattern
         ↓ .pipe(startWith(NaN)) ✅
┌────────────────────┐
│ _equity$           │ ✅ Emits NaN immediately
└────────┬───────────┘
         ↓ combineLatest fires!
┌────────────────────┐
│ combineLatest      │ ✅ Emits immediately
└────────┬───────────┘
         ↓
┌────────────────────┐
│ subscribe callback │ ✅ Called (sync works)
└────────────────────┘
```

### Solution Implementation

#### Approach: Add `startWith()` to Event-Based Observables

Match the pattern from the working Order dialog by adding `startWith()` operators to ensure immediate emission.

#### Implementation Details

**File**: `frontend/public/trading_terminal/bundles/order-view-controller.4f3dc6de299e33f3954b.js`

**Change 1: Add `startWith()` to `_quotes$`** (lines 5506-5513)

```javascript
// Before (BROKEN):
this._quotes$ = T(
  fromEventPattern(
    (e) => subscribeRealtime(position.symbol, e),
    (e, t) => t?.(),
  ),
)

// After (FIXED):
// NOTE: Must use startWith to ensure combineLatest in _parentPrice$ can emit
this._quotes$ = T(
  fromEventPattern(
    (e) => subscribeRealtime(position.symbol, e),
    (e, t) => t?.(),
  ).pipe((0, m.startWith)({ ask: position.avgPrice, bid: position.avgPrice })),
)
```

**Rationale**:

- Use `position.avgPrice` for both `ask` and `bid` as reasonable initial values
- Real quotes will replace these on first event from `subscribeRealtime`

**Change 2: Add `startWith()` to `_equity$`** (lines 5515-5523)

```javascript
// Before (BROKEN):
this._equity$ = T(
  fromEventPattern(
    (e) => subscribeEquity(position.symbol, e),
    (e, t) => t?.(),
  ),
)

// After (FIXED):
// NOTE: Must use startWith(NaN) to ensure combineLatest can emit immediately
this._equity$ = T(
  fromEventPattern(
    (e) => subscribeEquity(position.symbol, e),
    (e, t) => t?.(),
  ).pipe((0, m.startWith)(NaN)),
)
```

**Rationale**:

- Use `NaN` as safe default value (matches Order dialog pattern)
- Real equity value will replace `NaN` on first event from `subscribeEquity`
- `NaN` is safe for calculations (won't cause runtime errors)

#### Why These Default Values?

| Observable | Default Value                                        | Reasoning                                                                                        |
| ---------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `_quotes$` | `{ ask: position.avgPrice, bid: position.avgPrice }` | Use position's average price as initial bid/ask; most accurate estimate until real quotes arrive |
| `_equity$` | `NaN`                                                | Safe sentinel value; calculations handle `NaN` gracefully; matches Order dialog pattern          |

### Validation

**Test Case 1**: Stop Loss field sync

1. Open position edit dialog
2. Change Stop Loss **Price** from $165.00 to $170.00
3. **Expected**: Ticks and $ fields update immediately
4. **Result**: ✅ Fields sync instantly

**Test Case 2**: Take Profit field sync

1. Change Take Profit **Ticks** from 0 to +5
2. **Expected**: Price and $ fields update immediately
3. **Result**: ✅ Fields sync instantly

**User Confirmation**: January 13, 2026 - User confirmed field sync works perfectly.

---

## RxJS Patterns in TradingView Bundles

### Understanding `combineLatest` Behavior

**Core Rule**: `combineLatest` **waits for ALL source observables to emit at least once** before firing its subscription callback.

```javascript
// Example: All 3 must emit before callback fires
combineLatest({
  a: obs1$, // Must emit
  b: obs2$, // Must emit
  c: obs3$, // Must emit
}).subscribe(({ a, b, c }) => {
  console.log('All observables emitted:', a, b, c)
})
```

**Common Pitfall**: Forgetting `startWith()` on event-based observables

```javascript
// ❌ WRONG: obs2$ only emits on events, combineLatest may never fire
const obs2$ = fromEventPattern(subscribeToEvents)

// ✅ CORRECT: obs2$ emits default value immediately, combineLatest fires
const obs2$ = fromEventPattern(subscribeToEvents).pipe(startWith(defaultValue))
```

### Event-Based Observables: When to Use `startWith()`

**Pattern**: `fromEventPattern()` creates observables from event emitters

**Problem**: Only emits when events fire (may be delayed or never)

**Solution**: Add `startWith()` to provide initial value

```typescript
// ❌ Without startWith: waits for first event
const clicks$ = fromEventPattern(
  (handler) => button.addEventListener('click', handler),
  (handler) => button.removeEventListener('click', handler),
)

// ✅ With startWith: emits null immediately, then events
const clicks$ = fromEventPattern(
  (handler) => button.addEventListener('click', handler),
  (handler) => button.removeEventListener('click', handler),
).pipe(startWith(null))
```

### Observable Creation Patterns in TradingView

**Pattern 1: Immediate Emission (BehaviorSubject)**

```javascript
// Emits current value immediately on subscription
this._enabled$ = new BehaviorSubject(true)
```

**Pattern 2: Event-Based with Initial Value**

```javascript
// Emits default, then events
this._equity$ = fromEventPattern(subscribeEquity).pipe(
  startWith(NaN),
  share({ connector: () => new ReplaySubject(1) }),
)
```

**Pattern 3: Computed Observable (combineLatest)**

```javascript
// Emits whenever ANY source emits (after ALL emit once)
this._parentPrice$ = combineLatest({
  quotes: this._quotes$, // Must emit first
  equity: this._equity$, // Must emit first
}).pipe(map(({ quotes, equity }) => calculatePrice(quotes, equity)))
```

### Debugging RxJS Issues

#### Symptom: Subscription callback never fires

**Diagnosis Steps**:

1. **Add logging to subscription**:

```javascript
observable$.subscribe((value) => {
  console.log('[DEBUG] Observable emitted:', value)
})
```

2. **Check if `combineLatest` is involved**:

```javascript
// Log each source observable separately
quotes$.subscribe((v) => console.log('quotes$:', v))
equity$.subscribe((v) => console.log('equity$:', v))
combineLatest({ quotes$, equity$ }).subscribe((v) => console.log('combineLatest:', v))
```

3. **Verify all sources emit**:

```
Expected output:
quotes$: { ask: 170.50, bid: 170.48 }
equity$: 10000
combineLatest: { quotes: { ask: 170.50, bid: 170.48 }, equity: 10000 }

If combineLatest never logs → one source didn't emit
```

4. **Look for missing `startWith()`**:

```javascript
// Search bundle for fromEventPattern without startWith
grep -n "fromEventPattern" bundle.js | grep -v "startWith"
```

#### Symptom: Sync works after delay or manual interaction

**Root Cause**: Observable emits on user interaction (click, focus) instead of data change

**Solution**: Add `startWith()` to ensure immediate emission

---

## Common TradingView Bundle Issues

### Issue Category: Dialog Not Pre-Populating

**Symptoms**:

- Dialog fields empty when opening
- Data exists but isn't displayed
- Manual refresh required

**Root Causes**:

1. Data not passed through `customUI` hooks
2. TradingView doesn't fetch related data automatically
3. Interface mismatch (e.g., Position lacks bracket fields)

**Solution Pattern**:

```typescript
customUI: {
  showDialog: async (entity, relatedData) => {
    // Fetch missing related data
    const enrichedData = await fetchRelatedData(entity.id)

    // Call original dialog with enriched data
    return originalDialog(entity, enrichedData)
  }
}
```

**Example**: See [Case Study 1](#case-study-1-position-bracket-pre-population-bug)

---

### Issue Category: Fields Not Syncing

**Symptoms**:

- Changing one field doesn't update related fields
- Sync works after clicking other fields
- Sync works in some dialogs but not others

**Root Causes**:

1. RxJS `combineLatest` blocked by non-emitting observable
2. Missing `startWith()` on event-based observables
3. Incorrect observable dependencies

**Solution Pattern**:

```javascript
// ❌ BROKEN: Event observable without initial value
const eventObs$ = fromEventPattern(subscribeToEvents)

// ✅ FIXED: Add startWith for immediate emission
const eventObs$ = fromEventPattern(subscribeToEvents).pipe(startWith(defaultValue))
```

**Debugging Steps**:

1. Identify the sync handler (look for `combineLatest` subscriptions)
2. Add logging to verify if handler fires
3. Check all source observables for `startWith()`
4. Compare with working dialog (Order vs Position)

**Example**: See [Case Study 2](#case-study-2-position-dialog-field-sync-bug)

---

### Issue Category: Identifying Obfuscated Code

**Symptoms**:

- Need to understand minified class behavior
- Debugging requires readable parameter names
- Documentation needed for future maintenance

**Approach**:

**Step 1: Find Class Definition**

```bash
grep -n "class Pt " order-view-controller.*.js
# Output: 5333:class Pt {
```

**Step 2: Analyze Constructor Usage**

```javascript
// Look for class instantiation
new Pt(adapter, position, brackets, ...)
//     ^       ^         ^
//     |       |         |
//  param1   param2   param3
```

**Step 3: Map Parameters to Types**

```javascript
// Analyze parameter usage within class
constructor(e, t, n) {
  this._adapter = e         // e.getHost() → Trading Host → adapter
  this._position = t        // t.id, t.qty → Position interface
  this._brackets = n        // n.stopLoss, n.takeProfit → Brackets
}
```

**Step 4: Document in Comments or Guide**

```javascript
// class Pt = PositionViewModel
// constructor(
//   adapter: IBrokerConnectionAdapterHost,  // e
//   position: Position,                     // t
//   brackets: Brackets,                     // n
//   ...
// )
```

---

## Maintenance Best Practices

### 1. Preserve Original Code

**Rule**: Never delete original obfuscated code

**Rationale**:

- Maintains ability to revert changes
- Preserves exact behavior (whitespace, semicolons matter in minified code)
- Enables side-by-side comparison

**Acceptable Patterns**:

```javascript
// ✅ Pattern A: Add readable rewrite in comment
this._equity$ = T(fromEventPattern(o))
// Readable: this._equity$ = shareObservable(fromEventPattern(subscribeEquity))

// ✅ Pattern B: Add startWith while preserving original structure
this._equity$ = T(
  fromEventPattern(o).pipe((0, m.startWith)(NaN)), // ⬅ Only addition
)

// ❌ WRONG: Delete and replace original code
// this._equity$ = new BehaviorSubject(NaN)  // Don't do this!
```

---

### 2. Document Changes

**Rule**: Add comments explaining WHY changes were made

**Format**:

```javascript
// NOTE: [Description of issue]
// [Explanation of fix]
// [Date or issue reference]
modifiedCode()
```

**Example**:

```javascript
// NOTE: Must use startWith to ensure combineLatest in _parentPrice$ can emit
// Without this, the position dialog fields don't sync (Issue #123, Jan 2026)
.pipe((0, m.startWith)({ ask: position.avgPrice, bid: position.avgPrice }))
```

**What to Document**:

- Purpose of change (bug fix, feature addition)
- Root cause of original issue
- Why this specific solution was chosen
- Date or issue reference
- Validation results

---

### 3. Preserve Debug Logs

**Rule**: Comment out logs instead of deleting them

**Rationale**:

- Future maintainers can quickly re-enable for debugging
- Shows which values are important to inspect
- Preserves knowledge of data flow

**Pattern**:

```javascript
// Debug logs preserved for future troubleshooting:
// console.log('[Pt.constructor] Position:', position);
// console.log('[Pt.constructor] Brackets:', brackets);
// console.log('[Pt._subscribe] _equity$ emitted:', equity);
```

**When to Delete** (rare):

- Log reveals sensitive data (passwords, tokens)
- Log causes performance issues in production
- Code section being completely removed

---

### 4. Test Thoroughly

**Test Matrix**:

| Dialog       | Field Changes   | Expected Behavior           |
| ------------ | --------------- | --------------------------- |
| **Order**    | Price → Ticks/$ | Instant sync ✅             |
| **Order**    | Ticks → Price/$ | Instant sync ✅             |
| **Order**    | $ → Price/Ticks | Instant sync ✅             |
| **Position** | Price → Ticks/$ | Instant sync ✅ (after fix) |
| **Position** | Ticks → Price/$ | Instant sync ✅ (after fix) |
| **Position** | $ → Price/Ticks | Instant sync ✅ (after fix) |

**Edge Cases to Test**:

1. **Empty brackets**: Position with no TP/SL
2. **Partial brackets**: Position with only TP or only SL
3. **Multiple edits**: Rapid field changes
4. **Dialog cancellation**: Verify no side effects
5. **Error conditions**: Network failure during fetch

**Playwright Test Example**:

```typescript
test('position dialog fields sync correctly', async ({ page }) => {
  await openPositionDialog(page, 'POS-123')

  // Change Stop Loss price
  await page.locator('[data-field="stopLoss.price"]').fill('165.00')

  // Verify other fields updated immediately (no delay)
  await expect(page.locator('[data-field="stopLoss.ticks"]')).toHaveValue('-5.00')
  await expect(page.locator('[data-field="stopLoss.dollars"]')).toHaveValue('-$5.00')
})
```

---

### 5. Version Control Best Practices

**Commit Strategy**:

```bash
# Separate commits for different concerns
git commit bundle-file.js -m "fix: add startWith to position dialog observables"
git commit TraderChartContainer.vue -m "feat: enrich position brackets in customUI hook"
git commit BUNDLE-MAINTENANCE.md -m "docs: document position dialog fixes"
```

**Commit Message Format**:

```
<type>: <short summary>

<detailed explanation>
- Root cause: ...
- Solution: ...
- Validation: ...
```

**Types**: `fix`, `feat`, `docs`, `refactor`, `test`

**Bundle Version Tagging**:

```bash
# Tag bundle updates for easy rollback
git tag -a tradingview-v1.0.1 -m "Position dialog bracket fix"
git push origin tradingview-v1.0.1
```

---

## Reference: Key Classes

### `Pt` (PositionViewModel)

**Purpose**: Manages the position editing dialog UI and business logic

**Location**: `order-view-controller.js` line 5333

**Responsibilities**:

- Initialize position dialog state
- Create observable streams for sync
- Subscribe to equity/quote updates
- Handle bracket field synchronization
- Manage dialog lifecycle (open, edit, close)

**Key Properties**:

```javascript
this._adapter // IBrokerConnectionAdapterHost (Trading Host)
this._position // Position object
this._brackets // Brackets {stopLoss?, takeProfit?}
this._equity$ // Observable<number> - equity updates
this._quotes$ // Observable<Quotes> - realtime quotes
this._pipValues$ // Observable<PipValues> - pip value calculations
this._parentPrice$ // Observable<number> - current market price
```

**Key Methods**:

- `_createModels()`: Creates bracket models for TP/SL
- `_subscribe()`: Sets up RxJS subscriptions for field sync
- `destroy()`: Cleanup subscriptions and state

**Bug Fixed**: Added `startWith()` to `_equity$` and `_quotes$` for immediate emission (see Case Study 2)

---

### `bt` (OrderViewModel)

**Purpose**: Manages the order placement/editing dialog UI and business logic

**Location**: `order-view-controller.js` line 3509

**Responsibilities**:

- Initialize order dialog state
- Create observable streams (correctly includes `startWith`)
- Handle order preview/placement
- Manage bracket field synchronization
- Support various order types (Market, Limit, Stop, StopLimit)

**Key Difference from `Pt`**:

- **Works correctly** out of the box (has `startWith` on observables)
- Used as reference when debugging `Pt` class

**Observable Pattern** (correct):

```javascript
this._equity$ = fromEventPattern(subscribeEquity).pipe(
  startWith(NaN), // ✅ Immediate emission
  share({ connector: () => new ReplaySubject(1) }),
)
```

---

### `ie` (BracketModel)

**Purpose**: Manages individual bracket input controls (TP or SL) with multi-field sync

**Location**: `order-view-controller.js` line 261

**Responsibilities**:

- Sync 4 fields: Price, Ticks, $, %
- Convert between different bracket representations
- Handle focus control (which field user is editing)
- Calculate risk/reward based on position size and pip values

**Key Features**:

**1. Multi-Field Sync Mechanism**:

```javascript
combineLatest({
  enabled: this._enabled$,
  parentPrice: this._parentPrice$, // Current market price
  sideSign: this._sideSign$, // Buy (+1) or Sell (-1)
  pipValue: this._pipValue$, // $ per pip
  equity: this._equity$, // Account equity
  amount: this._amount$, // Position size
  bracketValuesWithFocusedControl: this._bracketValuesWithFocusedControl$,
}).subscribe(this._handleBracketsValuesChange)
```

**2. Field Types**:

```typescript
enum BracketFieldType {
  Price, // Absolute price ($165.00)
  Pips, // Distance in pips/ticks (-5.00)
  Currency, // Risk in $ (-$5.00)
  Percent, // Risk in % of equity (-0.05%)
}
```

**3. Focus Control**: Tracks which field user is editing to avoid overwriting their input

**4. Bidirectional Conversion**:

```
User enters Price → Calculate Pips, $, %
User enters Pips  → Calculate Price, $, %
User enters $     → Calculate Price, Pips, %
User enters %     → Calculate Price, Pips, $
```

**Dependencies**: Relies on `_equity$` and `_quotes$` from parent (`Pt` or `bt`) to function

---

### `gt` (PositionInfoModel)

**Purpose**: Displays position information table (leverage, tick value, trade value) in dialog

**Location**: `order-view-controller.js` line 5196

**Responsibilities**:

- Calculate and display position leverage
- Calculate tick value ($ per pip movement)
- Calculate total trade value
- Update display when position size changes

**Key Calculations**:

**Tick Value Formula**:

```typescript
tickValue = quantity × pipValue × lotSize
```

**Example** (GOOGL, 100 shares):

```
Quantity: 100 shares
Pip Size: $0.01
Pip Value: $0.01
Result: 100 × 0.01 = $1.00 per pip
```

**Usage**: See [Appendix: Tick Value Calculation](#appendix-tick-value-calculation)

---

## Appendix: Tick Value Calculation

### What is Tick Value?

**Tick Value** (also called **Pip Value**) is the **amount of money gained or lost per 1 pip (tick) of price movement**.

**Display**: "TICK VALUE: 1.00"

### Formula

```typescript
function calculatePipValue(qty: number, pipValue: number, lotSize?: number): number {
  return qty * pipValue * (lotSize || 1)
}
```

**Source**: `trading.js` line 7668

### Parameters

| Parameter  | Description                           | Example (GOOGL) |
| ---------- | ------------------------------------- | --------------- |
| `qty`      | Position quantity (shares, contracts) | 100 shares      |
| `pipValue` | Value of 1 pip                        | $0.01           |
| `lotSize`  | Multiplier for instruments (optional) | 1 (stocks)      |

### Example Calculation: GOOGL Position

**Scenario**: Long 100 shares of GOOGL at $170.50

**Inputs**:

- Quantity: 100 shares
- Pip Size: $0.01 (stocks move in $0.01 increments)
- Pip Value: $0.01

**Calculation**:

```
Tick Value = 100 × $0.01 × 1
           = $1.00 per pip
```

**Interpretation**:

- If GOOGL moves from $170.50 to $170.51 (+1 pip), P&L changes by +$1.00
- If GOOGL moves from $170.50 to $170.45 (-5 pips), P&L changes by -$5.00

### Usage in Bracket Fields

The tick value is used to calculate the **$ field** in TP/SL brackets:

**Example**: Stop Loss at $165.00 (current price $170.50)

```
Price Distance: $170.50 - $165.00 = $5.50
Ticks: $5.50 / $0.01 = -550 ticks (negative = below current price)
$ Risk: -550 × $1.00 = -$550.00
```

**Display in Dialog**:

- **Stop Loss Price**: $165.00
- **Ticks**: -550
- **$**: -$550.00

### Lot Size Multiplier

**Purpose**: Some instruments have multipliers (e.g., futures contracts)

**Example**: ES (S&P 500 Futures)

```
Quantity: 1 contract
Pip Value: $12.50 per pip
Lot Size: 1
Tick Value: 1 × $12.50 × 1 = $12.50 per pip
```

**Stock Example** (most common):

```
Lot Size: 1 (stocks don't have multipliers)
Tick Value: qty × pipValue × 1 = qty × pipValue
```

### Why Tick Value Matters

1. **Risk Calculation**: Helps traders calculate exact risk before placing orders
2. **Position Sizing**: Determines how much capital is at risk per pip movement
3. **TP/SL Placement**: Shows $ risk/reward for bracket levels
4. **Portfolio Management**: Enables precise risk management across multiple positions

---

**Last Updated**: January 13, 2026  
**Maintained by**: Development Team
