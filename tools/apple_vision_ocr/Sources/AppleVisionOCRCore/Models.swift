import Foundation

public struct BoundingBox: Codable, Equatable {
    public var x: Double
    public var y: Double
    public var width: Double
    public var height: Double

    public init(x: Double, y: Double, width: Double, height: Double) {
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    }
}

public struct ObservationCandidate: Codable, Equatable {
    public var text: String
    public var confidence: Double

    public init(text: String, confidence: Double) {
        self.text = text
        self.confidence = confidence
    }
}

public struct Observation: Codable, Equatable {
    public var text: String
    public var confidence: Double
    public var boundingBox: BoundingBox
    public var candidates: [ObservationCandidate]

    private enum CodingKeys: String, CodingKey {
        case text, confidence, candidates
        case boundingBox = "bounding_box"
    }

    public init(text: String, confidence: Double, boundingBox: BoundingBox, candidates: [ObservationCandidate]) {
        self.text = text
        self.confidence = confidence
        self.boundingBox = boundingBox
        self.candidates = candidates
    }
}

/// `apple-vision-ocr`が標準出力へ書き出すJSONのトップレベル構造。
public struct OCRRunResult: Codable, Equatable {
    public var engine: String
    public var available: Bool
    public var language: String
    public var durationSeconds: Double
    public var observations: [Observation]
    public var text: String
    public var warnings: [String]

    private enum CodingKeys: String, CodingKey {
        case engine, available, language, observations, text, warnings
        case durationSeconds = "duration_seconds"
    }

    public init(
        engine: String = "apple_vision",
        available: Bool,
        language: String,
        durationSeconds: Double,
        observations: [Observation],
        text: String,
        warnings: [String]
    ) {
        self.engine = engine
        self.available = available
        self.language = language
        self.durationSeconds = durationSeconds
        self.observations = observations
        self.text = text
        self.warnings = warnings
    }

    /// 利用不可・エラー時の結果を組み立てる（`available: false`、本文・観測結果は空）。
    public static func unavailable(language: String, warnings: [String], durationSeconds: Double = 0.0) -> OCRRunResult {
        OCRRunResult(
            available: false,
            language: language,
            durationSeconds: durationSeconds,
            observations: [],
            text: "",
            warnings: warnings
        )
    }
}

public enum JSONOutput {
    /// JSON文字列を組み立てる（`sortedKeys`で出力を安定させ、テスト・差分確認をしやすくする）。
    public static func encode(_ result: OCRRunResult) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys]
        guard let data = try? encoder.encode(result), let string = String(data: data, encoding: .utf8) else {
            // エンコード自体が失敗することは通常無いが、JSONを壊さないという要件のため、
            // 最低限のフォールバックJSONを直接組み立てて返す。
            return "{\"engine\":\"apple_vision\",\"available\":false,\"language\":\"\(language(result))\"," +
                "\"duration_seconds\":0,\"observations\":[],\"text\":\"\",\"warnings\":[\"json encode failed\"]}"
        }
        return string
    }

    private static func language(_ result: OCRRunResult) -> String {
        result.language
    }
}
