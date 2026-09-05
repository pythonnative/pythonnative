// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "PythonNativeKit",
    platforms: [.iOS(.v13)],
    products: [
        .library(name: "PythonNativeKit", targets: ["PythonNativeKit"]),
    ],
    targets: [
        .target(
            name: "PythonNativeKit",
            path: "Sources/PythonNativeKit"
        ),
        .testTarget(
            name: "PythonNativeKitTests",
            dependencies: ["PythonNativeKit"],
            path: "Tests/PythonNativeKitTests"
        ),
    ]
)
