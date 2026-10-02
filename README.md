# AppCatalog

Shared app names, localized short descriptions, App Store IDs and artwork for gewill apps. A small Swift Package with **no dependencies and no runtime network access**. UI and purchase logic stay in each host app.

## Included products

| Stable ID | Product | App Store ID | Artwork source |
| --- | --- | --- | --- |
| `iperfman` | iPerfman | `6447375831` | Public v1.6 |
| `clickman` | Clickman | `6449612559` | Public v1.3.4; transparent padding cropped |
| `secret-diary` | Secret Diary | `6445909382` | Public v2.0.1 |

Initial artwork was verified on 2026-10-02 in [Pingman PR #133](https://github.com/gewill/Pingman/pull/133). The 22 existing descriptions are carried over from Pingman, not a new translation review. English, Arabic, Danish, German, Spanish, Finnish, French, Hindi, Indonesian, Italian, Japanese, Korean, Norwegian Bokmål, Dutch, Polish, Portuguese, Russian, Swedish, Thai, Turkish, Simplified Chinese and Traditional Chinese are included.

The catalog is deliberately curated. Adding a record does not add it to every app. For example, Clickman is a Mac product; hosts decide whether to show it on other devices. iPerfman Pro (`6444657542`) is a distinct product and must not be conflated with the included iPerfman ID.

## Use from an app

Add `https://github.com/gewill/AppCatalog.git` in Xcode, select the `AppCatalog` library for each consuming target and pin an approved commit revision. Commit `Package.resolved`. After the first reviewed release, a version requirement can be used instead; no version tags are published yet.

```swift
import AppCatalog
import SwiftUI

// Load once, handle an invalid/missing bundle using the host's error policy.
let apps = try AppCatalog.load().select(["iperfman", "clickman", "secret-diary"])
// Empty selections are allowed; missing/duplicate IDs throw rather than disappear.

// In a SwiftUI view:
Image(app.iconName, bundle: AppCatalog.resources)
    .resizable()
    .frame(width: 80, height: 80)
    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
Text(LocalizedStringKey(app.name), tableName: "AppCatalog", bundle: AppCatalog.resources)
Text(LocalizedStringKey(app.subtitle), tableName: "AppCatalog", bundle: AppCatalog.resources)
Link("App Store", destination: app.storeURL(provider: "117201810", campaign: "MyHostApp"))
```

SwiftUI resolves text using the view's locale. For AppKit or a custom app language selector, look up the chosen `.lproj` bundle under `AppCatalog.resources` and use `localizedString(forKey:value:table:)` with table `AppCatalog`. Do not keep using `Bundle.main` for these strings or images. Verify fallback and actual language switching in the consumer.

Choose IDs and order explicitly; keep self-exclusion, platform eligibility, Pro visibility, attribution and layout local. A host with a fixed palette or carousel must handle its selected list length. Never derive attribution from another app's bundle name.

## Maintain the catalog

`catalog.json` and `icons/` are the source of truth. `Sources/AppCatalog/Resources/` is generated and checked in so consuming apps do not need Python or generation during builds. Localized `.strings` files keep the package usable with SwiftPM CLI and older supported app toolchains; all text is edited in the shared JSON.

1. Create an Issue and branch. Verify the exact public App Store product ID; do not substitute an unpublished local icon or merge separate paid/free products.
2. Update the relevant record and all declared translations. Keep `id` stable when a display name changes. Source-language `name`/`subtitle` are localization keys; colliding keys must have identical translations.
3. Save the public artwork in `icons/`, recording its URL, public version, retrieval date, original SHA-256, transform and resulting SHA-256. For Clickman, crop to the full alpha bounds `(46, 50, 466, 471)` (420×421), without resizing or dropping the last visible row. Do not automatically apply this crop to a future icon.
4. Run the checks below. Review the rendered artwork in a representative consumer in light/dark mode whenever pixels or displayed text change.
5. Commit and push, open a PR and wait for checks/review. After merge, each host updates its pinned revision in its own PR. Installed apps change only when their app update ships.

```sh
python3 scripts/catalog.py validate
python3 scripts/catalog.py generate
python3 scripts/catalog.py generate --check
python3 -m unittest discover -s tests -v
swift test
git diff --check
```

Validation checks identity, translations, source provenance, file signatures, hashes and path boundaries. The generator refuses output drift in check mode. Swift tests check loading, selection, encoded attribution and localized resource access. Xcode consumer builds and screenshots verify compiled asset catalogs; a SwiftPM command-line test is not visual acceptance.

## Adoption

- [Pingman #138](https://github.com/gewill/Pingman/issues/138): initial integration, preserve the existing three rows and presentation.
- OpenCCman: compatible active consumer, not migrated yet; retains its own three-language UI and Pro visibility policy.
- Clickman: existing recommendation code belongs to an older screen; its current AppKit entry needs separate design before enabling recommendations.
- iPerfman / Secret Diary: no current My Apps entry was found; adding one is outside this repository's initial scope.

Public repository access is not a license to reuse app branding. Icons, names and product artwork remain the property of their respective owners and are included here for these apps' product links. No credentials, ASC private metadata, pricing claims or analytics are stored here.
