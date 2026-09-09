import XCTest
@testable import PythonNativeKit

final class PNContractFixtureTests: XCTestCase {
    func testPortableFixtures() throws {
        let file = try XCTUnwrap(Bundle.module.url(forResource: "validation", withExtension: "json", subdirectory: "Fixtures"))
        let cases = try JSONSerialization.jsonObject(with: Data(contentsOf: file)) as! [[String: Any]]
        for item in cases {
            XCTAssertEqual(PNContracts.matches(item["value"]!, item["schema"] as! [String: Any]), item["valid"] as! Bool, item["name"] as! String)
        }
    }
}
