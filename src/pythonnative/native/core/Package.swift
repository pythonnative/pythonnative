// swift-tools-version: 5.9
import PackageDescription

// The renderer core (RFC 0007) and the Yoga release it embeds, built from the
// same sources as Android's libpncore.so and the host extension.
let package = Package(
    name: "PNCore",
    platforms: [.iOS(.v13)],
    products: [.library(name: "PNCore", targets: ["PNCore"])],
    targets: [
        .target(
            name: "PNCore",
            path: ".",
            exclude: [
                "CMakeLists.txt", "python.cpp",
                "yoga/CMakeLists.txt", "yoga/LICENSE", "yoga/VENDORED.md", "yoga/module.modulemap",
            ],
            sources: ["src", "yoga"],
            publicHeadersPath: "include",
            cxxSettings: [.headerSearchPath(".")]
        ),
    ],
    cxxLanguageStandard: .cxx20
)
