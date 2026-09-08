// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "YogaCore",
    products: [.library(name: "YogaCore", targets: ["YogaCore"])],
    targets: [.target(name: "YogaCore", path: ".", exclude: ["yoga/CMakeLists.txt", "yoga/module.modulemap"], sources: ["yoga", "style.cpp"],
                      publicHeadersPath: "include", cxxSettings: [.headerSearchPath(".")])],
    cxxLanguageStandard: .cxx20
)
