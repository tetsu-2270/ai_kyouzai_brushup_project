import Foundation

/// `apple-vision-ocr`の入力引数。
public struct Arguments: Equatable {
    public var inputPath: String
    public var language: String
    public var recognitionLevel: String
    public var languageCorrection: Bool
    public var customWords: [String]

    public init(
        inputPath: String,
        language: String = "ja-JP",
        recognitionLevel: String = "accurate",
        languageCorrection: Bool = false,
        customWords: [String] = []
    ) {
        self.inputPath = inputPath
        self.language = language
        self.recognitionLevel = recognitionLevel
        self.languageCorrection = languageCorrection
        self.customWords = customWords
    }
}

/// 引数解析エラー（コマンドの使い方が誤っている場合）。
public struct ArgumentError: Error, Equatable, CustomStringConvertible {
    public let message: String
    public init(_ message: String) {
        self.message = message
    }
    public var description: String { message }
}

public enum ArgumentParser {
    /// `--input`/`--language`/`--recognition-level`/`--language-correction`/`--custom-words`を解析する。
    ///
    /// `--input`のみ必須。他は省略時に既定値（`ja-JP`/`accurate`/補正なし/カスタム単語なし）を使う。
    /// `--custom-words`はカンマ区切りで複数指定できる（例: `--custom-words キャラ設定,おとスタ`）。
    public static func parse(_ arguments: [String]) -> Result<Arguments, ArgumentError> {
        var inputPath: String?
        var language = "ja-JP"
        var recognitionLevel = "accurate"
        var languageCorrection = false
        var customWords: [String] = []

        var index = 0
        while index < arguments.count {
            let token = arguments[index]
            switch token {
            case "--input":
                guard let value = valueAfter(arguments, index) else {
                    return .failure(ArgumentError("--input には値が必要です"))
                }
                inputPath = value
                index += 2
            case "--language":
                guard let value = valueAfter(arguments, index) else {
                    return .failure(ArgumentError("--language には値が必要です"))
                }
                language = value
                index += 2
            case "--recognition-level":
                guard let value = valueAfter(arguments, index) else {
                    return .failure(ArgumentError("--recognition-level には値が必要です"))
                }
                guard value == "accurate" || value == "fast" else {
                    return .failure(ArgumentError("--recognition-level は accurate または fast を指定してください"))
                }
                recognitionLevel = value
                index += 2
            case "--language-correction":
                languageCorrection = true
                index += 1
            case "--custom-words":
                guard let value = valueAfter(arguments, index) else {
                    return .failure(ArgumentError("--custom-words には値が必要です"))
                }
                customWords = value
                    .split(separator: ",")
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { !$0.isEmpty }
                index += 2
            default:
                return .failure(ArgumentError("不明な引数です: \(token)"))
            }
        }

        guard let resolvedInputPath = inputPath else {
            return .failure(ArgumentError("--input は必須です"))
        }

        return .success(
            Arguments(
                inputPath: resolvedInputPath,
                language: language,
                recognitionLevel: recognitionLevel,
                languageCorrection: languageCorrection,
                customWords: customWords
            )
        )
    }

    private static func valueAfter(_ arguments: [String], _ index: Int) -> String? {
        let nextIndex = index + 1
        guard nextIndex < arguments.count else { return nil }
        return arguments[nextIndex]
    }
}

public let usageText = """
apple-vision-ocr --input <画像パス> [--language ja-JP] [--recognition-level accurate|fast] \
[--language-correction] [--custom-words 単語1,単語2]

macOS標準のVisionフレームワーク（VNRecognizeTextRequest）でローカルOCRを実行し、
結果をJSONとして標準出力へ出力します。画像やOCR結果を外部へ送信することはありません。
"""
