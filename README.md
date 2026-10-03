# AppCatalog

[![Catalog checks](https://github.com/gewill/AppCatalog/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/gewill/AppCatalog/actions/workflows/ci.yml)

One place to maintain the app names, short descriptions, App Store IDs and icons used by gewill's **My Apps** recommendations.

AppCatalog is a Swift Package with no external dependencies. Data, images and translations ship inside each app, so displaying recommendations requires no network request. Each host keeps its own interface and decides which products to show.

## Products and languages

| Stable ID | Product | App Store ID | Current artwork |
| --- | --- | --- | --- |
| `iperfman` | [iPerfman](https://apps.apple.com/app/id6447375831) | `6447375831` | v2.0 original Icon Composer PNG |
| `clickman` | [Clickman](https://apps.apple.com/app/id6449612559) | `6449612559` | Public v1.3.4; transparent padding cropped |
| `secret-diary` | [Secret Diary](https://apps.apple.com/app/id6445909382) | `6445909382` | Public v2.0.1 |

Names and descriptions cover **22 locales**: `en`, `ar`, `da`, `de`, `es`, `fi`, `fr`, `hi`, `id`, `it`, `ja`, `ko`, `nb`, `nl`, `pl`, `pt`, `ru`, `sv`, `th`, `tr`, `zh-Hans` and `zh-Hant`.

Initial artwork was checked on **2026-10-02** in [Pingman PR #133](https://github.com/gewill/Pingman/pull/133). iPerfman v2.0 was verified through Apple’s public record on **2026-10-03**; its artwork uses the original 1024×1024 PNG from the single-layer Icon Composer source, without the store rendition’s baked-in outer frame ([Issue #5](https://github.com/gewill/AppCatalog/issues/5)). Descriptions preserve Pingman's existing translations; this migration was not a new linguistic review. [catalog.json](catalog.json) records each image's source URL, version, retrieval date, transform and SHA-256.

Adding a product here does **not** automatically add a row to any app. Clickman is a Mac product; hosts decide where to recommend it. iPerfman Pro (`6444657542`) is a separate App Store product, not the included `iperfman` record.

## Shared data, local presentation

| AppCatalog owns | The host app owns |
| --- | --- |
| Stable product IDs and App Store IDs | Selection, order, self-exclusion and platform eligibility |
| Names and localized descriptions | Language preference and general UI labels |
| Bundled icons and provenance | Layout, image size, clipping and accessibility |
| Encoded App Store URLs | Attribution, opening links, Pro visibility and navigation |

The package provides no recommendation screen, runtime metadata fetching, analytics or purchase logic.

## Requirements

- Swift tools **5.9+**.
- Declared deployment minimums: **iOS/iPadOS 15**, **macOS 12**, **tvOS 15**. Mac Catalyst uses the iOS minimum. These are compatibility declarations, not a claim that every platform has been visually tested.
- Xcode compiles the image asset catalog; command-line SwiftPM tests do not establish rendered-icon correctness.
- Maintainers need **Python 3.9+**, with no third-party packages. Consuming apps need neither Python nor a generation build phase.

## Add the package

In Xcode, add the URL below and link the **AppCatalog** product to every consuming target:

```text
https://github.com/gewill/AppCatalog.git
```

Select **Commit** and pin the initial implementation merged in [PR #2](https://github.com/gewill/AppCatalog/pull/2):

```text
5c94b45666301a571e1c166603ad5be0774ffdc6
```

Commit both the project change and `Package.resolved`. No version tags exist as of 2026-10-02; use a reviewed revision rather than a nonexistent version or a moving branch.

For a SwiftPM host, add these entries to its `Package.swift`:

```swift
// In dependencies:
.package(
    url: "https://github.com/gewill/AppCatalog.git",
    revision: "5c94b45666301a571e1c166603ad5be0774ffdc6"
)

// In the consuming target's dependencies:
.product(name: "AppCatalog", package: "appcatalog")
```

### Load once and select explicitly

```swift
import AppCatalog

func loadRecommendations() throws -> [CatalogApp] {
    try AppCatalog.load().select(["iperfman", "clickman", "secret-diary"])
}
```

`select` preserves the requested order. An empty selection returns an empty array; unknown or repeated IDs throw. Loading can also fail because of missing, unreadable or invalid resources. Handle these errors using the host's policy; optional recommendations should not prevent its primary function from running.

### Display in SwiftUI

Pass the loaded products to the view rather than loading the catalog in `body`. Adapt this presentation to the host:

```swift
import AppCatalog
import SwiftUI

struct RecommendedApps: View {
    let apps: [CatalogApp]

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            ForEach(apps) { app in
                Link(destination: app.storeURL()) {
                    HStack(spacing: 12) {
                        Image(app.iconName, bundle: AppCatalog.resources)
                            .resizable()
                            .frame(width: 80, height: 80)
                            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                            .accessibilityHidden(true)
                        VStack(alignment: .leading) {
                            Text(LocalizedStringKey(app.name),
                                 tableName: "AppCatalog", bundle: AppCatalog.resources)
                                .font(.headline)
                            Text(LocalizedStringKey(app.subtitle),
                                 tableName: "AppCatalog", bundle: AppCatalog.resources)
                                .font(.subheadline)
                        }
                    }
                }
                .accessibilityElement(children: .combine)
            }
        }
    }
}
```

For attributed links, use `app.storeURL(provider: "117201810", campaign: "MyHostApp")` with the host's own values. Omit the arguments for a plain store URL. `URLComponents` encodes query values; do not pre-encode or manually concatenate them.

### Language and resource lookup

- Names and subtitles are English source keys. Resolve them through `LocalizedStringKey`, table **AppCatalog**, bundle **AppCatalog.resources**. Images use that bundle too; `Bundle.main` does not own these resources.
- SwiftUI `Text` uses the view's locale. Keep the host's locale environment when users change language.
- For AppKit/manual lookup, match the requested locale against `AppCatalog.resources.localizations` case-insensitively, open that actual `.lproj` name, and call `localizedString(forKey:value:table:)`. Native SwiftPM may lowercase names such as `zh-hans.lproj`.
- Manual lookup needs an explicit fallback, for example requested locale → supported language → English. The package does not map `zh_CN` to `zh-Hans` or provide locale negotiation; the host handles mapping and refreshing displayed text.

Verify live language switching, fallback and persistence in each host. A resource lookup test alone does not validate its language selector.

## Maintain the catalog

| Location | Purpose | Edit directly? |
| --- | --- | --- |
| [catalog.json](catalog.json) | Product records, translations and artwork provenance | Yes |
| [icons/](icons/) | Normalized PNG/JPEG artwork | Yes |
| [Sources/AppCatalog/Resources/](Sources/AppCatalog/Resources/) | Generated JSON, asset catalog and localized `.strings` | No |
| [scripts/catalog.py](scripts/catalog.py) | Offline validation and generation | For tooling changes |
| [Sources/AppCatalog/AppCatalog.swift](Sources/AppCatalog/AppCatalog.swift) | Public Swift API | For behavior changes |

Generated resources are committed so consuming apps can build directly. Edit translations in the shared JSON, not in generated `.strings` files or host copies.

1. **Create an Issue and branch.** Verify the public App Store ID; do not substitute unpublished artwork or combine paid/free products.
2. **Update the canonical data.** Keep `id` stable when names change. Complete every declared locale. Reused source keys must have identical translations.
3. **Record artwork provenance.** Include the source URL, public version, retrieval date, original SHA-256, transform and final SHA-256. Inspect changed artwork visually.
4. **Regenerate and validate.** Run the checks below. Include real before/after consumer captures when visible content changes.
5. **Commit, push and open a PR.** After checks and review, squash-merge to `main`.
6. **Update consumers separately.** Each host pins the approved merge revision, updates its lockfile and verifies the affected UI in its own PR. Installed apps change only when those app updates ship.

The initial Clickman image uses alpha bounds `(46, 50, 466, 471)`, producing 420×421 pixels without resizing. This transform belongs to that source image; re-evaluate the bounds for future artwork.

## Validation

For catalog, resource or generator changes:

```sh
python3 scripts/catalog.py validate
python3 scripts/catalog.py generate
python3 scripts/catalog.py generate --check
python3 -m unittest discover -s tests -v
swift test
git diff --check
```

`validate` checks IDs, locale coverage, key conflicts, provenance fields, image signatures, hashes and paths. It does not re-query Apple or establish that recorded artwork is still current. `generate --check` is read-only: exit `0` means current, `1` means drift, and `2` means invalid input or an execution error.

| Change | Validation scope |
| --- | --- |
| README-only | Check claims, links and examples; run `git diff --check` |
| Catalog or artwork | Validate/regenerate, run package tests, inspect affected consumer UI |
| API, generator or package configuration | Run relevant Python/Swift tests and affected consumer builds |

[CI](.github/workflows/ci.yml) runs catalog/package checks on a GitHub-hosted Ubuntu runner and cancels superseded runs. It does not run every app's regression suite. Consumers retain their required checks and release acceptance.

## Integration status

Checked on **2026-10-02**; linked PRs are the source for subsequent changes.

| Project | Status |
| --- | --- |
| AppCatalog | [Initial package merged](https://github.com/gewill/AppCatalog/pull/2); no version tag yet |
| Pingman | [Integration PR #139](https://github.com/gewill/Pingman/pull/139) open. Native Mac build, light/dark and language checks completed; adoption not merged or released |
| OpenCCman | Existing recommendation UI; not migrated. Pro visibility rules stay in the host |
| Clickman | Recommendation code belongs to an older screen; its current AppKit interface needs a separate integration decision |
| iPerfman / Secret Diary | No current My Apps entry found in the initial audit; adding one is separate product work |

## Artwork and privacy

Public repository access does not grant a license to reuse app branding. Names, icons and artwork remain the property of their respective owners and are included for these apps' product links.

No credentials, private App Store Connect metadata, pricing claims or analytics are stored here. See [AGENTS.md](AGENTS.md) for contribution constraints.
