import Foundation

/// Product information and artwork shipped with the host app. No network access.
public struct CatalogApp: Decodable, Identifiable, Equatable, Sendable {
    public let id: String
    public let appStoreID: String
    /// English source key. Resolve in `AppCatalog.resources`, table `AppCatalog`.
    public let name: String
    public let subtitle: String

    public var iconName: String { "AppCatalog-\(id)" }

    /// Attribution belongs to the host rather than the shared product record.
    public func storeURL(provider: String? = nil, campaign: String? = nil) -> URL {
        var components = URLComponents()
        components.scheme = "https"
        components.host = "apps.apple.com"
        components.path = "/app/apple-store/id\(appStoreID)"
        var query: [URLQueryItem] = []
        if let provider, !provider.isEmpty {
            query.append(URLQueryItem(name: "pt", value: provider))
        }
        if let campaign, !campaign.isEmpty {
            query.append(URLQueryItem(name: "ct", value: campaign))
        }
        if !query.isEmpty { query.append(URLQueryItem(name: "mt", value: "8")) }
        components.queryItems = query.isEmpty ? nil : query
        // Scheme, host and path are controlled; URLComponents escapes query values.
        return components.url!
    }
}

public struct AppCatalog: Sendable {
    public enum CatalogError: Error, Equatable {
        case missingResource
        case unsupportedSchema
        case invalidProducts
        case unknownProduct(String)
        case duplicateSelection
    }

    public let apps: [CatalogApp]
    public static var resources: Bundle { .module }

    /// Throws on malformed bundled data so a host can provide its own fallback.
    public static func load() throws -> AppCatalog {
        guard let url = resources.url(forResource: "catalog", withExtension: "json") else {
            throw CatalogError.missingResource
        }
        return try AppCatalog(data: Data(contentsOf: url))
    }

    public init(data: Data) throws {
        struct Document: Decodable {
            let schemaVersion: Int
            let apps: [CatalogApp]
        }
        let document = try JSONDecoder().decode(Document.self, from: data)
        guard document.schemaVersion == 1 else { throw CatalogError.unsupportedSchema }
        let apps = document.apps
        guard !apps.isEmpty,
              Set(apps.map(\.id)).count == apps.count,
              Set(apps.map(\.appStoreID)).count == apps.count,
              apps.allSatisfy({ !$0.id.isEmpty && !$0.name.isEmpty && !$0.subtitle.isEmpty
                  && !$0.appStoreID.isEmpty && $0.appStoreID.utf8.allSatisfy({ (48...57).contains($0) }) })
        else { throw CatalogError.invalidProducts }
        self.apps = apps
    }

    /// Explicit host selection: adding products to the catalog cannot add UI rows.
    public func select(_ ids: [String]) throws -> [CatalogApp] {
        guard Set(ids).count == ids.count else { throw CatalogError.duplicateSelection }
        let byID = Dictionary(uniqueKeysWithValues: apps.map { ($0.id, $0) })
        return try ids.map { id in
            guard let app = byID[id] else { throw CatalogError.unknownProduct(id) }
            return app
        }
    }
}
