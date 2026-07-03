# sansan-competition

`kimu` 担当の土台として、Google Classroom の提出状況を正規化し、判定し、GUI 班へ返す構造化 JSON を生成する実装を追加しています。

## 含めたもの

- `sansan_competition/normalization.py`
  - `Course` / `CourseWork` / `StudentSubmission` の正規化
  - 部分失敗を許容する `normalize_submission_batch`
- `sansan_competition/analysis.py`
  - 未提出
  - 期限接近未提出
  - 遅延提出
  - 添付不足の可能性
  の判定ロジック
- `sansan_competition/contract.py`
  - `schemaVersion=1.0.0` の共通レスポンス組み立て
  - 正常系、部分成功、異常系の返却
  - GUI 向け `summary` / `gui` / `outputs` / `approval` / `errors`
  - 契約検証用のバリデータ
- `sansan_competition/outputs.py`
  - Markdown / PDF / Google Document 用の構造化データ
  - Classroom 投稿 payload
- `schemas/agent-output-v1.0.0.json`
  - GUI 班との契約として渡せる JSON Schema
- `samples/*.json`
  - 正常系と異常系のサンプル JSON

## 設計上の前提

- エラー時も GUI の分岐を減らすため、`gui` / `outputs` / `approval` を空で返す固定形にしています。
- `添付不足の可能性` は、`ASSIGNMENT` または `SHORT_ANSWER_QUESTION` で `TURNED_IN` / `RETURNED` だが添付ゼロの場合のヒューリスティックです。実際の提出内容確認は別途必要です。
- `partial_success` を導入し、一部データだけ正規化できたケースを `errors` と `warnings` に残します。

## 実行例

```bash
python3 main.py
```

## テスト

```bash
python3 -m unittest discover -s tests
```
