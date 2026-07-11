// swift-tools-version:5.9
import PackageDescription

// テスト構成についての注記:
// 本来はSwiftPMの`.testTarget`（XCTest/Swift Testing）を使うのが標準的だが、この開発環境には
// Xcode本体が無くCommand Line Toolsのみのため、`swift test`はXCTest/Swift Testingいずれも
// 実行時にTesting.framework/XCTest.frameworkの解決に失敗し動作しなかった（Xcode本体が無い環境の
// 既知の制約）。そのため、Foundationのみに依存する軽量な自作テストハーネス実行ファイル
// （AppleVisionOCRSelfTests）をテストとして採用している。Xcodeが利用できる環境では、
// 通常の`.testTarget`へ戻すことも可能。

let package = Package(
    name: "AppleVisionOCR",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "apple-vision-ocr", targets: ["apple-vision-ocr"])
    ],
    targets: [
        // Vision呼び出し・引数解析・JSON組み立てのロジック本体。
        // 実行ファイル本体から分離することで、テストから直接ロジックを検証できるようにする。
        .target(
            name: "AppleVisionOCRCore",
            dependencies: []
        ),
        // 薄い実行ファイル。CommandLine.argumentsを読み、AppleVisionOCRCoreへ委譲するだけ。
        .executableTarget(
            name: "apple-vision-ocr",
            dependencies: ["AppleVisionOCRCore"]
        ),
        // Foundationのみに依存する自作テストハーネス（上記注記参照）。
        // `swift run AppleVisionOCRSelfTests`で実行し、失敗があれば非ゼロ終了する。
        .executableTarget(
            name: "AppleVisionOCRSelfTests",
            dependencies: ["AppleVisionOCRCore"]
        ),
    ]
)
