import AppleVisionOCRCore
import Foundation

let harness = TestHarness()

// --- ArgumentParser ---------------------------------------------------------------------

harness.run("missingInputFails") {
    let result = ArgumentParser.parse([])
    guard case .failure(let error) = result else {
        throw TestFailure(message: "--inputが無いのに成功した")
    }
    try harness.expect(error.description.contains("--input"), "エラーメッセージに--inputが含まれていない: \(error.description)")
}

harness.run("inputWithoutValueFails") {
    let result = ArgumentParser.parse(["--input"])
    guard case .failure = result else {
        throw TestFailure(message: "--inputに値が無いのに成功した")
    }
}

harness.run("defaultsAreAppliedWhenOnlyInputGiven") {
    let result = ArgumentParser.parse(["--input", "/tmp/example.png"])
    guard case .success(let arguments) = result else {
        throw TestFailure(message: "失敗してはいけない")
    }
    try harness.expect(arguments.inputPath == "/tmp/example.png")
    try harness.expect(arguments.language == "ja-JP")
    try harness.expect(arguments.recognitionLevel == "accurate")
    try harness.expect(arguments.languageCorrection == false)
    try harness.expect(arguments.customWords == [])
}

harness.run("allOptionsAreParsed") {
    let result = ArgumentParser.parse([
        "--input", "/tmp/example.png",
        "--language", "ja-JP",
        "--recognition-level", "fast",
        "--language-correction",
        "--custom-words", "キャラ設定, おとスタ,実践タイム",
    ])
    guard case .success(let arguments) = result else {
        throw TestFailure(message: "失敗してはいけない")
    }
    try harness.expect(arguments.recognitionLevel == "fast")
    try harness.expect(arguments.languageCorrection == true)
    try harness.expect(arguments.customWords == ["キャラ設定", "おとスタ", "実践タイム"])
}

harness.run("invalidRecognitionLevelFails") {
    let result = ArgumentParser.parse(["--input", "/tmp/example.png", "--recognition-level", "ultra"])
    guard case .failure = result else {
        throw TestFailure(message: "不正なrecognition-levelなのに成功した")
    }
}

harness.run("unknownArgumentFails") {
    let result = ArgumentParser.parse(["--input", "/tmp/example.png", "--bogus"])
    guard case .failure = result else {
        throw TestFailure(message: "未知の引数なのに成功した")
    }
}

// --- Models（JSON） ----------------------------------------------------------------------

harness.run("encodeIncludesRequiredTopLevelFields") {
    let result = OCRRunResult(
        available: true,
        language: "ja-JP",
        durationSeconds: 1.234,
        observations: [
            Observation(
                text: "テスト",
                confidence: 0.9,
                boundingBox: BoundingBox(x: 0.1, y: 0.2, width: 0.3, height: 0.05),
                candidates: [ObservationCandidate(text: "テスト", confidence: 0.9)]
            )
        ],
        text: "テスト",
        warnings: []
    )
    let json = JSONOutput.encode(result)
    let requiredKeys = [
        "\"engine\"", "\"available\"", "\"language\"", "\"duration_seconds\"", "\"observations\"",
        "\"text\"", "\"warnings\"", "\"bounding_box\"", "\"candidates\"", "\"confidence\"",
    ]
    for key in requiredKeys {
        try harness.expect(json.contains(key), "JSON出力に\(key)が含まれていない: \(json)")
    }
    try harness.expect(json.contains("apple_vision"))
}

harness.run("unavailableResultHasEmptyTextAndObservations") {
    let result = OCRRunResult.unavailable(language: "ja-JP", warnings: ["image not found"])
    try harness.expect(result.available == false)
    try harness.expect(result.text == "")
    try harness.expect(result.observations.isEmpty)
    try harness.expect(result.warnings == ["image not found"])
}

harness.run("encodedJSONRoundTripsThroughDecoder") {
    let original = OCRRunResult(
        available: true,
        language: "ja-JP",
        durationSeconds: 0.5,
        observations: [],
        text: "サンプル本文",
        warnings: ["軽微な警告"]
    )
    let json = JSONOutput.encode(original)
    let decoded = try JSONDecoder().decode(OCRRunResult.self, from: Data(json.utf8))
    try harness.expect(decoded == original)
}

// --- VisionRunner（実OCR結果の完全一致は検証しない。構造面のみ） -------------------------------

harness.run("missingImageReturnsUnavailableWithExitCode2") {
    let arguments = Arguments(inputPath: "/tmp/does-not-exist-\(UUID().uuidString).png")
    let (result, exitCode) = VisionOCRRunner.run(arguments)
    try harness.expect(result.available == false)
    try harness.expect(exitCode == 2, "exitCode=\(exitCode)")
    try harness.expect(!result.warnings.isEmpty)
}

harness.run("supportedLanguagesIsNonEmptyOnThisPlatform") {
    let languages = VisionAvailability.supportedLanguages(recognitionLevel: "accurate")
    try harness.expect(!languages.isEmpty, "この環境でVisionの対応言語が1つも取得できなかった")
}

harness.run("unsupportedLanguageIsReportedAsUnsupported") {
    try harness.expect(!VisionAvailability.isLanguageSupported("xx-unsupported-lang", recognitionLevel: "accurate"))
}

harness.summaryAndExit()
