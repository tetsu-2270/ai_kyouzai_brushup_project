# 07 API連携設計（将来拡張のための設計メモ）

> 補足: 本メモが想定するAPI/LLM連携は未実装のままです。現状の`restructure`/`generate`モード（[`docs/00_redesign_v2.md`](00_redesign_v2.md)・[`docs/01_requirements.md`](01_requirements.md)参照）は、いずれも外部API・LLMを使わないルールベース実装です。将来これらをLLM連携に置き換える場合、本メモの方針（コアと分離したアダプタ層、`pyproject.toml`の`optional-dependencies`分離等）がそのまま適用できる想定です。

## 目的
現状はOCR・ブラッシュアップ・Canva設計のいずれも「`prompts/`配下のプロンプトをAIチャットに貼り、人が結果を`pages`JSON（docs/03）にまとめる」手動フローである。将来これらをAPI経由で自動化する場合の設計方針をまとめる。

本フェーズは設計のみとし、実装は行わない。CLAUDE_RULES.mdの「外部API前提にしない」「有料サービス前提にしない」を維持するため、以下のアダプタは未実装のままとする。

## 方針
- `pages`JSON形式（docs/03）を、API連携時も共通のデータ交換フォーマットとして維持する。API出力は必ずこの形式に変換してからCLIに渡す。
- 外部API呼び出しは`src/`のコア（`models.py`/`parser.py`/`renderer.py`/`canva_renderer.py`）に直接組み込まず、独立した「アダプタ」層として追加する（例: 将来`src/providers/`配下に追加）。コアはJSON入力のみに依存し続け、APIの有無に関わらず動作する。
- 外部パッケージが必要になった場合は`pyproject.toml`の`optional-dependencies`に分離し（例: `[project.optional-dependencies] api = [...]`）、標準インストールでは不要にする。
- APIキー等の秘密情報はコードに直書きせず、環境変数または`.gitignore`済みの設定ファイルから読む。

## 想定する拡張ポイント
1. **文字起こしAPI連携**: 画像を渡してOCR/画像読解APIを呼び出し、`prompts/ocr_transcription_prompt.md`と同じ出力（`page_no`/`source_image`/`title`/`lines`/`unreadable_parts`）をJSONで受け取るアダプタ。`unreadable_parts`が空でない場合は自動でpagesに投入せず、人の確認を必須にする。
2. **ブラッシュアップAPI連携**: `lines`と教材方針を渡し、`summary`・`improvement_points`の下書きを生成するアダプタ。生成結果は必ず人が確認してから`pages`JSONへ反映する（「元教材の意図を無視して文章を大きく改変しない」という方針を維持するため、`lines`自体をAPIが書き換えることはしない）。
3. **Canva設計API連携**: `lines`・`summary`を渡し、`canva.layout_type`/`main_visual`/`notes`の下書きを生成するアダプタ。最終的な「Canva AI投入用プロンプト」は引き続き`canva_renderer.py`がJSONから自動生成する。

## 段階的な導入方針
- Phase 3時点: 上記アダプタは未実装。プロンプトを人が手動でAIに投入し、結果を`pages`JSONへ反映する運用を継続する。
- Phase 4以降: 必要になった時点で、ユーザーの承認を得たうえで`src/providers/`にアダプタを追加する。既存のCLIコマンド体系・データ形式（docs/03）・出力形式（docs/04）は変更しない。

## 非対象
- 特定のAPIベンダー（OCR/LLM等）を前提にした実装は、この設計では確定しない。ベンダー選定はPhase 4着手時に別途相談する。
- 有料APIの利用を必須にする変更は行わない。既存の手動フロー（プロンプトをコピーして使う）は今後も動作し続ける。
