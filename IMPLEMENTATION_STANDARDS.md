# Implementation Standards & Engineering Guidelines

### Implementation Standards

* Understand the relevant architecture, conventions, callers, and tests before editing.
* Prefer simple, maintainable solutions and reuse existing project patterns and utilities.
* Keep changes focused on the requested task; do not add dependencies or unrelated refactors without a clear need.
* Consider validation, error handling, performance, backward compatibility, and dependent functionality.
* No mock, dummy, static, hardcoded, or fake implementations. Every feature and endpoint must perform its actual intended functionality using the real services, database, authentication/session state, external APIs, or other required integrations. No placeholder success responses should be used where real business logic is required.

### Regression Safety and Testing

Before making a meaningful change, identify the affected code path and its relevant callers, APIs, database queries, jobs, and frontend consumers. Afterward, test the changed behavior and relevant related behavior, run appropriate existing tests, and fix regressions caused by the change.

* Add or update tests where appropriate; do not weaken or bypass tests to make them pass.
* Run the relevant tests and broader checks when the change may have wider effects.
* If tests cannot be run, state why.
* Use code comments only for non-obvious business logic, architectural decisions, external limitations, security-sensitive behavior, or important edge cases.

### Repository Exploration

Start with targeted investigation: identify the relevant route, service, component, model, utility, or job; search for callers and dependencies; inspect relevant tests; then expand only as needed for correctness and regression safety.

### Completion Checklist

Before considering work complete, verify:

* [ ] Requested functionality is implemented.
* [ ] Project patterns and relevant edge cases were considered.
* [ ] Appropriate tests were added or updated and relevant tests were run, or the reason they could not run is stated.
* [ ] Relevant existing functionality was checked for regressions.
* [ ] No unrelated changes or exposed secrets were introduced.
* [ ] Nothing was pushed to the remote repository unless explicitly requested.
* [ ] All implemented features are fully functional and production-ready; no mock, dummy, static, hardcoded, fake, or placeholder implementations remain.

When reporting completion, briefly state what changed, tests and results, and any remaining concerns or limitations.

### Git Safety

**Never push code unless the user explicitly asks.** Do not push branches, create or
update pull requests, or mark pull requests ready for review without explicit request.
Local commits are allowed when useful, but do not push them.

### Duplication

Make sure the same functionality or code is not implemented again in any other way. For example:
```python
app.include_router(health_router, prefix=api_prefix)
app.include_router(health_router)
```
Both are logically and conceptually the same, so avoid such mistakes. Always maintain single, canonical implementations and route definitions.
