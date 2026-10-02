// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AppCatalog",
    defaultLocalization: "en",
    platforms: [.iOS(.v15), .macOS(.v12), .tvOS(.v15)],
    products: [.library(name: "AppCatalog", targets: ["AppCatalog"])],
    targets: [
        .target(name: "AppCatalog", resources: [.process("Resources")]),
        .testTarget(name: "AppCatalogTests", dependencies: ["AppCatalog"], path: "tests/AppCatalogTests"),
    ]
)
