import Foundation
import XCTest
@testable import AppCatalog

final class AppCatalogTests: XCTestCase {
    func testBundledCatalogAndExplicitOrdering() throws {
        let catalog = try AppCatalog.load()
        XCTAssertEqual(try catalog.select(["clickman", "iperfman"]).map(\.appStoreID),
                       ["6449612559", "6447375831"])
        XCTAssertEqual(try catalog.select([]), [])
        XCTAssertThrowsError(try catalog.select(["missing"]))
        XCTAssertThrowsError(try catalog.select(["clickman", "clickman"]))
        XCTAssertEqual(catalog.apps.count, 8)
    }

    func testAttributionIsEncodedWithoutAddingQueryParameters() throws {
        let app = try XCTUnwrap(AppCatalog.load().apps.first)
        let plain = try XCTUnwrap(URLComponents(url: app.storeURL(), resolvingAgainstBaseURL: false))
        XCTAssertNil(plain.query)
        let components = try XCTUnwrap(URLComponents(
            url: app.storeURL(provider: "117201810", campaign: "Pingman & Mac/简中?"),
            resolvingAgainstBaseURL: false))
        XCTAssertEqual(components.host, "apps.apple.com")
        XCTAssertEqual(components.queryItems?.map(\.name), ["pt", "ct", "mt"])
        XCTAssertEqual(components.queryItems?[1].value, "Pingman & Mac/简中?")
    }

    func testChineseResourceLookup() throws {
        let locale = try XCTUnwrap(AppCatalog.resources.localizations.first {
            $0.caseInsensitiveCompare("zh-Hans") == .orderedSame
        })
        let path = try XCTUnwrap(AppCatalog.resources.path(forResource: locale, ofType: "lproj"))
        let bundle = try XCTUnwrap(Bundle(path: path))
        let key = "Password Protected Diary"
        XCTAssertNotEqual(bundle.localizedString(forKey: key, value: nil, table: "AppCatalog"), key)
    }

    func testMalformedSchemaAndProductDataAreRejected() throws {
        XCTAssertThrowsError(try AppCatalog(data: Data("{\"schemaVersion\":2,\"apps\":[]}".utf8)))
        let invalid = """
        {"schemaVersion":1,"apps":[{"id":"app","appStoreID":"123?x=y","name":"App","subtitle":"Test"}]}
        """
        XCTAssertThrowsError(try AppCatalog(data: Data(invalid.utf8)))
    }
}
