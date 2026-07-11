import Foundation

/// Xcode本体が無い環境でも動く、Foundationのみに依存した最小限のテストハーネス
/// （`Package.swift`の冒頭コメント参照）。
final class TestHarness {
    private(set) var passed = 0
    private(set) var failed = 0
    private var currentTestName = ""

    func run(_ name: String, _ body: () throws -> Void) {
        currentTestName = name
        do {
            try body()
            passed += 1
            print("PASS: \(name)")
        } catch let error as TestFailure {
            failed += 1
            print("FAIL: \(name) — \(error.message)")
        } catch {
            failed += 1
            print("FAIL: \(name) — 予期しない例外: \(error)")
        }
    }

    func expect(_ condition: @autoclosure () -> Bool, _ message: String = "", file: String = #file, line: Int = #line) throws {
        if !condition() {
            throw TestFailure(message: message.isEmpty ? "assertion failed (\(file):\(line))" : message)
        }
    }

    func summaryAndExit() -> Never {
        print("---")
        print("結果: \(passed) passed, \(failed) failed (合計 \(passed + failed))")
        exit(failed == 0 ? 0 : 1)
    }
}

struct TestFailure: Error {
    let message: String
}
