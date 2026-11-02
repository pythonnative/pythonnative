import Foundation
import PNC_e2e_checksum

/// Exercises a plugin's C target and an `Info.plist` key it declares.
public enum ChecksumPlugin: PNPlugin {
    public static func register(into registry: PNRegistry) {
        registry.registerModule(ChecksumModuleAdapter<ChecksumModule>.self)
    }
}

final class ChecksumModule: ChecksumImplementation {
    init() {}

    func adler32(text: String) -> Int64 {
        let bytes = Array(text.utf8)
        return Int64(pn_e2e_adler32(bytes, bytes.count))
    }

    func configured_value() -> String {
        Bundle.main.object(forInfoDictionaryKey: "PNE2EPluginKey") as? String ?? "missing"
    }
}
