# AppCatalog

Shared product data and resources, not shared promotional UI.

- Work through Issue → branch → PR. `main` is the integration branch; use `codex/<issue>-<topic>`.
- `catalog.json` and `icons/` are canonical. Never edit generated `Sources/AppCatalog/Resources/` directly.
- Preserve source URL, public version, retrieval date and SHA-256 when updating artwork. Keep transforms explicit; do not regenerate branded artwork with AI.
- Keep all declared locales complete. Product IDs are stable, not localized names. Separate distinct App Store products even if they share a brand.
- Host apps choose order, placement, platform eligibility, self-exclusion, Pro gating and attribution. Do not add runtime requests, analytics, UI or purchases to this package.
- Run validator, generator check, Python tests, `swift test` and `git diff --check` as appropriate. Do not run downstream apps' full regression suites for metadata-only changes.
- Visible changes need real representative before/after captures in the consumer PR. Generated images are not UI validation.
- Updating this repository does not modify installed apps. Consumers update a pinned package revision/version through their own PR and release process.
