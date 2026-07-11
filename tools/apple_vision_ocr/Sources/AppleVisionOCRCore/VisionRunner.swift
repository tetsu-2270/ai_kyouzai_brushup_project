import Foundation
import ImageIO
import Vision

public enum VisionAvailability {
    /// 指定した言語が、この環境のVisionテキスト認識でサポートされているかどうかを確認する。
    ///
    /// 画像を読み込まずに確認できるため、実際のOCR実行前の事前診断・テストの両方で使える。
    /// macOS・Visionのバージョンによっては`ja-JP`が使えない場合があり、その場合は
    /// 呼び出し側が分かりやすいエラーメッセージを返せるようにする。
    public static func supportedLanguages(recognitionLevel: String) -> [String] {
        let level: VNRequestTextRecognitionLevel = (recognitionLevel == "fast") ? .fast : .accurate
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = level
        do {
            return try request.supportedRecognitionLanguages()
        } catch {
            return []
        }
    }

    public static func isLanguageSupported(_ language: String, recognitionLevel: String) -> Bool {
        supportedLanguages(recognitionLevel: recognitionLevel).contains(language)
    }
}

public enum ImageLoadError: Error, CustomStringConvertible {
    case fileNotFound(String)
    case unreadableImage(String)

    public var description: String {
        switch self {
        case .fileNotFound(let path):
            return "画像ファイルが見つかりません: \(path)"
        case .unreadableImage(let path):
            return "画像を読み込めませんでした（対応していない形式の可能性があります）: \(path)"
        }
    }
}

public enum ImageLoader {
    public static func loadCGImage(path: String) -> Result<CGImage, ImageLoadError> {
        guard FileManager.default.fileExists(atPath: path) else {
            return .failure(.fileNotFound(path))
        }
        let url = URL(fileURLWithPath: path)
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
            return .failure(.unreadableImage(path))
        }
        return .success(image)
    }
}

public enum VisionOCRRunner {
    /// 画像1枚に対してVisionでOCRを実行し、`OCRRunResult`を返す。
    ///
    /// 例外を投げず、失敗時は常に`available: false`かつ`warnings`に理由を含む結果を返す
    /// （呼び出し元＝実行ファイルが、失敗理由に応じたJSON出力・終了コードを決められるようにするため）。
    public static func run(_ arguments: Arguments) -> (result: OCRRunResult, exitCode: Int32) {
        let started = Date()

        switch ImageLoader.loadCGImage(path: arguments.inputPath) {
        case .failure(let error):
            let duration = Date().timeIntervalSince(started)
            return (
                OCRRunResult.unavailable(language: arguments.language, warnings: [error.description], durationSeconds: duration),
                2
            )
        case .success(let cgImage):
            guard VisionAvailability.isLanguageSupported(arguments.language, recognitionLevel: arguments.recognitionLevel) else {
                let duration = Date().timeIntervalSince(started)
                let supported = VisionAvailability.supportedLanguages(recognitionLevel: arguments.recognitionLevel)
                let warning = "言語 \(arguments.language) はこの環境のVisionでサポートされていません" +
                    "（対応言語: \(supported.joined(separator: ", "))）"
                return (
                    OCRRunResult.unavailable(language: arguments.language, warnings: [warning], durationSeconds: duration),
                    3
                )
            }

            let request = VNRecognizeTextRequest()
            request.recognitionLevel = (arguments.recognitionLevel == "fast") ? .fast : .accurate
            request.usesLanguageCorrection = arguments.languageCorrection
            request.recognitionLanguages = [arguments.language]
            if !arguments.customWords.isEmpty {
                request.customWords = arguments.customWords
            }

            let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
            do {
                try handler.perform([request])
            } catch {
                let duration = Date().timeIntervalSince(started)
                return (
                    OCRRunResult.unavailable(
                        language: arguments.language,
                        warnings: ["Vision実行時にエラーが発生しました: \(error.localizedDescription)"],
                        durationSeconds: duration
                    ),
                    4
                )
            }

            let observations = request.results ?? []
            let built = observations.map { observation -> Observation in
                let topCandidates = observation.topCandidates(3)
                let best = topCandidates.first
                let boundingBox = BoundingBox(
                    x: observation.boundingBox.origin.x,
                    y: observation.boundingBox.origin.y,
                    width: observation.boundingBox.size.width,
                    height: observation.boundingBox.size.height
                )
                let candidates = topCandidates.map { ObservationCandidate(text: $0.string, confidence: Double($0.confidence)) }
                return Observation(
                    text: best?.string ?? "",
                    confidence: Double(best?.confidence ?? 0),
                    boundingBox: boundingBox,
                    candidates: candidates
                )
            }

            // Visionはbounding boxのy座標が下端基準（画像下=0）で返るため、上から下へ読む順序に
            // 並べ替えるにはyの降順（画像上部ほどyが大きい）→ 同程度の高さならxの昇順、で並べる。
            let ordered = built.sorted { lhs, rhs in
                if abs(lhs.boundingBox.y - rhs.boundingBox.y) > 0.01 {
                    return lhs.boundingBox.y > rhs.boundingBox.y
                }
                return lhs.boundingBox.x < rhs.boundingBox.x
            }

            let fullText = ordered.map { $0.text }.joined(separator: "\n")
            let duration = Date().timeIntervalSince(started)
            let result = OCRRunResult(
                available: true,
                language: arguments.language,
                durationSeconds: duration,
                observations: ordered,
                text: fullText,
                warnings: []
            )
            return (result, 0)
        }
    }
}
