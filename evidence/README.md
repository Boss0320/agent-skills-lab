# Evaluation evidence / 評估證據

## English

This directory contains the sanitized aggregate that public copy is allowed to
quote. It does not contain raw model transcripts, evaluator prompts, hidden
answers, private paths, or production data.

The result is an offline quality regrade of 25 preserved result receipts from a
frozen synthetic paired set. No model call was added or replaced. Artifact size
was retained as cost telemetry but was not treated as a quality veto.

| Skill | Without | With | Bounded reading |
|---|---:|---:|---|
| Integration audit | 0/3 | 2/3 | Professional packet quality improved; semantic detection stayed 3/3 → 3/3. |
| Dual-lens review | 0/6 | 6/6 | Typed lens delivery improved; reconciliation moved 0/3 → 3/3. Raw reasoning was not scored. |
| Anime production director | 0/2 | 2/2 | Storyboard/workflow artifacts improved. Blind preference and finished-media quality are unavailable. |

Each case currently has one paired run. These results support a limited claim
about structured delivery and workflow behavior in this set. They do not support
a statistically strong benchmark or a universal capability claim.

The authoritative public aggregate is
[`benchmark-summary.json`](benchmark-summary.json). Its source receipt is bound
by SHA-256, without exposing the internal evidence path.

## 繁體中文

這個資料夾只保留公開文案可以引用的去識別彙總結果，不包含原始模型對話、評分提示、
隱藏答案、私人路徑或 production 資料。

目前結果是對凍結合成對照案例的 25 份既有執行收據進行離線品質重評；沒有新增或替換模型呼叫。
產物大小仍保留為成本資訊，但不再被誤當成作品品質的一票否決。

| Skill | 無 Skill | 有 Skill | 可支持的解讀 |
|---|---:|---:|---|
| 系統整合稽核 | 0/3 | 2/3 | 專業封包品質改善；語意偵測維持 3/3 → 3/3。 |
| 雙視角投資複核 | 0/6 | 6/6 | 交付格式改善；合併判定由 0/3 → 3/3。未評分自由推理能力。 |
| AI 動畫製作導演 | 0/2 | 2/2 | 分鏡與製作流程產物改善；盲測偏好與最終成片品質皆無可用證據。 |

每個案例目前只有一組成對執行。這能支持「在本批案例中改善結構化交付與流程行為」的有限說法，
不能宣稱已形成具有統計強度的 benchmark，也不能推廣成普遍能力提升。
