---
name: tradingview-bundle
description: TradingView bundle maintenance and debugging. Load when debugging TV bundle issues or patching obfuscated JS
keywords: [tradingview, bundle, obfuscated, rxjs, patching]
category: tradingview
disable-model-invocation: true
---

# TradingView Bundle Maintenance

Methodology for debugging, patching, and maintaining the forked TradingView Trading Terminal obfuscated bundles. This is a reverse-engineering discipline — no vendor support exists.

---

## When to Use This Skill

- Debugging TradingView dialog issues (order ticket, position panel, account manager)
- Investigating field sync problems (values not updating, stale calculations)
- Patching bundle behavior (adding `startWith()`, fixing observable chains)
- Understanding obfuscated class structures in bundle files
- Tracing RxJS observable flows in minified code
- Adding console logging to bundle code for investigation

---

## Bundle Architecture

```
frontend/public/trading_terminal/bundles/
├── order-view-controller.*.js   # Order/Position dialog logic (PATCHED)
├── trading.*.js                 # Core trading operations, calculations
├── trading-account-manager.*.js # Account Manager UI components
└── ... (100+ other bundle files)
```

| Bundle | Key Classes | Responsibility |
|--------|-------------|----------------|
| order-view-controller.js | `Pt` (PositionViewModel), `bt` (OrderViewModel), `ie` (BracketModel) | Dialog view models |
| trading.js | Trading utilities | Calculations (pip value, tick size) |
| trading-account-manager.js | Account panel components | Account Manager UI |

---

## Methodology

### Phase 1: Locate Target Code

1. **Identify the symptom** — Which dialog/panel/feature is broken?
2. **Map symptom → bundle** — Use class map below to find the right bundle file
3. **Search for class declaration**: `grep -n "class Pt " order-view-controller.*.js`
4. **Open file at target line** and read surrounding context

### Phase 2: Unobfuscate

Map cryptic parameter names by usage analysis:

| Technique | How |
|-----------|-----|
| **Method calls** | `e.getHost()` → Trading Host adapter |
| **Property access** | `t.id`, `t.qty` → Position interface |
| **RxJS patterns** | `pipe`, `subscribe` → Observable |
| **Cross-reference** | Compare with types in `charting_library.d.ts` / `broker-api.d.ts` |

**Output options** (pick one per situation):
- **Inline comments**: `e, // adapter: IBrokerConnectionAdapterHost`
- **Side-by-side rewrite**: Original preserved, readable version commented below
- **Documentation**: Record mappings in BUNDLE-MAINTENANCE.md

### Phase 3: Instrument & Debug

**Console logging strategy:**
```javascript
// ✅ GOOD: Contextual, structured, prefixed with class.method
console.log('[ie.subscribe] combineLatest emitted:', {
  enabled: values.enabled,
  parentPrice: values.parentPrice,
  pipValue: values.pipValue,
  equity: values.equity,
})

// ❌ BAD: Generic, no context
console.log('value:', values)
```

**Where to add logs**: Constructor calls, observable emissions, subscription handlers, error paths.

### Phase 4: Diagnose Root Cause

Common patterns:
| Symptom | Likely Cause | Diagnostic |
|---------|-------------|------------|
| Fields don't sync on input | Missing `startWith()` on observable | Check `combineLatest` — are ALL source observables emitting? |
| Dialog opens with empty fields | Data not passed through hook | Log parameters in `customUI.showPositionDialog` |
| Values update only on click | `combineLatest` blocked until manual interaction | Trace which observable hasn't emitted yet |
| Silent failures | Nullish keys in discriminated unions | Check objects passed to `host.*Update()` methods |

### Phase 5: Apply Fix & Preserve

**Fix application rules:**
1. **NEVER delete original code** — always preserve minified version
2. Add readable version alongside: `// Original: T(fromEventPattern(o))`
3. Keep debug logs as comments: `// console.log('[Pt.constructor]...`
4. Document the fix in BUNDLE-MAINTENANCE.md with case study format

---

## Obfuscated Class Map

| Minified | Actual | Location | Purpose |
|----------|--------|----------|---------|
| `Pt` | PositionViewModel | order-view-controller.js | Position dialog state management |
| `bt` | OrderViewModel | order-view-controller.js | Order dialog state management |
| `ie` | BracketModel | order-view-controller.js | SL/TP bracket field sync logic |
| `gt` | (varies) | order-view-controller.js | Supporting view model |
| `T()` | `shareObservable()` | Various | RxJS share helper |
| `m.startWith` | `startWith()` | RxJS imports | Initial value for observables |

**Naming patterns:**
- Classes: Single/double uppercase letters (`Pt`, `bt`, `ie`)
- Methods: Camelcase with underscores (`_createModels`, `_subscribe`)
- Observables: End with `$` (`_equity$`, `_quotes$`, `_pipValues$`)

---

## RxJS Patterns in Bundles

### combineLatest Blockage (Most Common Issue)

```javascript
// combineLatest ONLY fires after ALL observables emit at least once
combineLatest({ equity: _equity$, quotes: _quotes$, ... }).subscribe(handler)
// If _equity$ never emits → handler NEVER fires → fields never sync
```

**Fix**: Add `startWith()` to event-based observables:
```javascript
// Before (broken): fromEventPattern(subscribeEquity)
// After (fixed):   fromEventPattern(subscribeEquity).pipe(startWith(NaN))
```

### fromEventPattern → Observable Bridge

```javascript
fromEventPattern(
  (handler) => subscribeRealtime(symbol, handler),  // subscribe
  (handler, unsubscribe) => unsubscribe?.()          // unsubscribe
)
```

### shareObservable (T helper)

Wraps observable with `share({ connector: () => new ReplaySubject(1) })` for multicasting.

---

## Anti-Patterns

- ❌ **Deleting original minified code** — always preserve for diff and rollback
- ❌ **Removing console.log statements** — comment them out instead, future debuggers need them
- ❌ **Modifying without documenting** — every patch MUST have a case study in BUNDLE-MAINTENANCE.md
- ❌ **Guessing parameter meanings** — always trace usage to confirm before renaming
- ✅ **Systematic unobfuscation** — map parameters → instrument → diagnose → fix → document

---

## Resources

Primary documentation (read the relevant case study before starting):

- [BUNDLE-MAINTENANCE.md](../../../../frontend/docs/tradingview/BUNDLE-MAINTENANCE.md) — Full maintenance guide with case studies (~1,300 lines)
- [public/README.md](../../../../frontend/public/README.md) — Bundle overview, modification history, maintenance workflow
