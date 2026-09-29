// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PythonNativeKit",
    platforms: [.iOS(.v13)],
    products: [
        .library(name: "PythonNativeKit", targets: ["PythonNativeKit"]),
    ],
    dependencies: [
        .package(path: "../yoga"),
        // pn:packages
        // pn:end-packages
    ],
    targets: [
        .target(
            name: "PythonNativeKit",
            dependencies: [
                .product(name: "YogaCore", package: "yoga"),
                // pn:products
                // pn:end-products
            ],
            path: "Sources/PythonNativeKit",
            resources: [.process("Resources")]
        ),
        .testTarget(
            name: "PythonNativeKitTests",
            dependencies: ["PythonNativeKit"],
            path: "Tests/PythonNativeKitTests",
            resources: [.copy("Fixtures")]
        ),
    ]
)
