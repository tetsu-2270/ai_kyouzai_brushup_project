import AppleVisionOCRCore
import Foundation

// 実行ファイル本体はCommandLine.argumentsの解析とVisionOCRRunnerへの委譲のみを行う。
// ロジック本体はAppleVisionOCRCore（XCTestからユニットテスト可能）に置く。

let rawArguments = Array(CommandLine.arguments.dropFirst())

switch ArgumentParser.parse(rawArguments) {
case .failure(let error):
    FileHandle.standardError.write(Data((error.description + "\n\n" + usageText + "\n").utf8))
    exit(64) // EX_USAGE
case .success(let arguments):
    let (result, exitCode) = VisionOCRRunner.run(arguments)
    print(JSONOutput.encode(result))
    exit(exitCode)
}
