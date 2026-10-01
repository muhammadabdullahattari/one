### Frontend Implementation Standards (Next.js, shadcn/ui, TanStack Query, TanStack Virtual, Apache ECharts)
* Understand the existing routes, layouts, components, hooks, API client, design tokens, and tests before editing.
* Reuse existing components, hooks, utilities, and patterns. Do not create a second version of something that already exists.
* Keep changes focused on the requested task; do not add dependencies, UI libraries, or state managers without a clear need.
* No mock, dummy, static, hardcoded, or fake data in production code. Every screen must use real endpoints, real authentication/session state, and real data. No `setTimeout`-faked responses or placeholder success states.

### Next.js
* Follow the project's App Router conventions. Server Components are the default; add `"use client"` only for interactivity, browser APIs, or hooks, and keep client boundaries as low in the tree as possible.
* Define `loading.tsx`, `error.tsx`, and `not-found.tsx` at the route level where applicable, instead of re-implementing those states inside each page.
* Never put secrets in `NEXT_PUBLIC_*` variables. Server-only configuration stays server-only.
* Use `next/image`, `next/font`, and `next/link`. Use `next/dynamic` for heavy client-only components.
* Enforce route protection in middleware for UX, but the backend remains the authority on permissions.
* Use environment-based configuration for API URLs and feature flags. No hardcoded URLs or ports.

### shadcn/ui and Styling
* Add new primitives with the shadcn CLI into the project's `components/ui` directory. Do not hand-write lookalikes.
* Compose or wrap primitives rather than editing them in place; if an in-place edit is project-wide, note why.
* Use design tokens and CSS variables for colors, spacing, and typography. No hardcoded hex values or magic numbers.
* Use the shared `cn()` helper for class merging, and do not introduce another styling approach.
* Preserve Radix accessibility behavior (focus management, ARIA, keyboard support) when customizing.

### API Integration
* Generate types and the API client from the backend OpenAPI schema. Do not hand-edit generated files; regenerate them when the contract changes.
* All requests go through the single canonical API client, which owns the base URL, auth, and error normalization. No ad hoc `fetch`/`axios` calls in components.
* Wrap the client in typed TanStack Query hooks with centralized, consistent query keys.
* Keep request and response types aligned with the backend: field names, nullability, pagination, and error shapes.
* Mutations must invalidate or update the affected queries. Optimistic updates must roll back on failure.
* Handle cancellation (`AbortSignal`), retries, and stale-response races.
* Do not mirror server data into local state; the query cache is the single source of truth.

### Authentication and Session
* Use the project's single auth mechanism (httpOnly cookies preferred). Do not store tokens in `localStorage` unless that is the approved pattern.
* Handle 401 with a single refresh-and-retry flow that prevents refresh stampedes, then redirect to login if refresh fails.
* Handle 403 with an explicit forbidden state, never a silent failure.
* On logout or session expiry, clear the query cache, close WebSockets, and reset client state.
* Client-side role checks are for UX only; the backend must enforce authorization.

### WebSocket
* Use one shared connection manager per endpoint. Do not open sockets from individual components.
* Implement reconnection with exponential backoff and jitter, heartbeat handling, and resubscription after reconnect.
* Authenticate the socket with the same mechanism as REST and handle token expiry on long-lived connections.
* Define typed message schemas aligned with the backend, validate incoming messages, and safely ignore unknown types.
* Merge live updates into the TanStack Query cache instead of keeping a parallel store.
* Batch or throttle high-frequency messages so updates stay within the frame budget.
* Show connection status to the user and clean up on unmount and logout.

### Virtualized Lists (TanStack Virtual)
* Virtualize any list, table, or grid that can exceed a few hundred rows.
* Use stable, unique keys (record IDs, never array indexes).
* Provide a realistic `estimateSize`, and use `measureElement` for dynamic row heights.
* Keep rows memoized and free of heavy work or data fetching.
* Combine with server-side pagination or infinite queries instead of loading the full dataset.
* Preserve scroll position and accessibility (`aria-rowcount`, focusable rows, keyboard navigation).

### Charts (Apache ECharts)
* Import only the required modules from `echarts/core`. Do not import the full bundle.
* Use one reusable chart wrapper that handles init, resize (`ResizeObserver`), theming, and `dispose()` on unmount. Do not initialize ECharts ad hoc in pages.
* Render charts client-side only (`next/dynamic` with `ssr: false`).
* Feed charts real API data, and use merge-style `setOption` updates for streaming data instead of rebuilding the chart.
* For large or high-frequency series, use sampling, `large` mode, or progressive rendering, and disable animation.
* Provide loading, empty, and error states plus an accessible alternative (`aria` options, text summary, or data table).
* Take chart colors from the design tokens so light and dark themes stay consistent.

### UI States, Forms, and Error Handling
* Every data-driven view handles loading, empty, error, and success states, plus partial or stale data where relevant.
* Show actionable, user-friendly error messages. Never swallow errors silently or expose stack traces or internal details.
* Prevent duplicate submissions with in-flight guards and disabled controls.
* Client validation is for usability only; server validation is the source of truth, and server errors must be surfaced in the UI.
* Keep client validation rules aligned with the backend, and preserve user input on failed submissions.

### Accessibility and Responsiveness
* Use semantic HTML, proper labels, roles, and alt text. Ensure full keyboard navigation and visible focus states.
* Maintain sufficient color contrast and do not convey meaning by color alone.
* Verify layouts at mobile, tablet, and desktop breakpoints, with no horizontal overflow.
* Use the project's i18n mechanism and shared formatting utilities if they exist; no hardcoded user-facing strings in that case.

### Security
* Never expose secrets, API keys, or tokens in frontend code, bundles, or logs. Anything shipped to the client is public.
* Avoid `dangerouslySetInnerHTML`, `innerHTML`, and `eval`. If unavoidable, sanitize with an established library.
* Do not log sensitive data to the console or error reporting.

### Performance
* Target 60 FPS: a 16.7 ms frame budget, with no long tasks (>50 ms) during scrolling, interaction, or live updates.
* Avoid unnecessary re-renders and redundant or duplicate requests. Debounce search and input-triggered requests.
* Lazy-load heavy routes and components, and optimize images and assets.
* Clean up subscriptions, timers, listeners, observers, and in-flight requests on unmount.
* Measure with real traces (Performance API, React Profiler, Playwright with Chrome tracing) on the production build with realistic data volumes.
* Track Core Web Vitals (LCP, INP, CLS) and bundle size. Do not loosen a performance threshold to make a check pass.

### Frontend Testing
* Add or update Vitest component and hook tests for changed behavior, including loading, empty, error, and validation states.
* Query by role, label, and text with React Testing Library, not by class names or implementation details.
* Network mocking (e.g., MSW) is allowed in unit and component tests only, never in production code, and handlers must match the real API contract.
* Test virtualized lists by asserting visible-window behavior. For ECharts, test the wrapper lifecycle (init, update, dispose) and option-building logic, mocking only at the canvas boundary.
* Add Playwright E2E tests for critical flows. Use role- or label-based locators, web-first assertions, and isolated tests; no fixed sleeps or `waitForTimeout`.
* Reuse authenticated storage state instead of logging in through the UI in every test.
* Run key flows on desktop and mobile viewports, and run accessibility checks (axe) on key pages.
* Do not weaken, skip, or bypass tests to make them pass.
* Run the linter, type checker, formatter, unit tests, and a production build, and fix any regressions you introduced.

### Integration Testing
* Run Playwright against the real backend, real database, and real auth. No `page.route` stubs, MSW, or other mocks.
* Use a dedicated test environment with seeded, isolated data. Never test against production.
* Create test data through real APIs or seed scripts and clean it up afterward. Tests must not depend on leftover state.
* Cover login and logout, session expiry and refresh, CRUD, server validation errors, 403 denial, and empty and error states.
* Verify WebSocket behavior end to end: live updates, reconnection after a dropped connection, and auth failures.
* Verify charts and virtualized lists with real data at realistic volumes.
* Assert on both UI results and backend side effects where it matters.
* Fix flaky tests instead of masking them with retries.
* Run in CI against the production build, and keep traces, screenshots, and videos for failures.
* If the real backend cannot be run, state why. Do not substitute mocks and call it integration testing.

### Regression Safety (Frontend)
* Before changing a shared component, hook, query key, or style, identify every page and component that uses it.
* Verify the changed flow in a browser when possible, including related pages that share the changed code.
* Check that backend contract changes (fields, status codes, WebSocket messages) do not break existing consumers.
* If something cannot be verified, state why.

### Duplication (Frontend)
Make sure the same component, hook, route, or request is not implemented in more than one way. For example:
```tsx
// Duplicate routes and duplicate data fetching for the same resource
app/users/page.tsx
app/(dashboard)/users/page.tsx

const { data } = useUsers();
const res = await fetch("/api/users");
```
Both pairs are conceptually the same, so avoid them. Keep one canonical route definition, one typed hook, and one API client path per resource.

### Frontend Completion Checklist
Before considering frontend work complete, verify:
* [ ] Requested functionality is implemented using real endpoints, auth, and data.
* [ ] Server and Client Component boundaries are correct, with route-level loading, error, and not-found states.
* [ ] Existing components, hooks, shadcn/ui primitives, and design tokens were reused, with no duplicated routes, components, or API calls.
* [ ] API types and hooks match the OpenAPI contract, and generated files were regenerated, not hand-edited.
* [ ] Loading, empty, error, and success states are handled, with duplicate submissions prevented.
* [ ] Auth, 401 refresh, 403 handling, and logout cleanup were verified.
* [ ] WebSocket usage goes through the single manager, with reconnect, validation, and throttled cache updates.
* [ ] Large lists are virtualized with stable keys, and ECharts instances are tree-shaken, client-only, and disposed on unmount.
* [ ] Accessibility, responsiveness, security, and 60 FPS performance were reviewed.
* [ ] Vitest, Playwright UI tests, and Playwright integration tests (against the real backend) were run, or the reason they could not run is stated.
* [ ] Lint, type check, and production build pass.
* [ ] Related pages and components were checked for regressions.
* [ ] No debug code, `console.log`, commented-out code, TODO stubs, secrets, or unrelated changes were introduced.
* [ ] Nothing was pushed to the remote repository unless explicitly requested.

When reporting completion, briefly state what changed, tests and results, and any remaining concerns or limitations.
