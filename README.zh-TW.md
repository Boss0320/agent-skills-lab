# Agent Skills Lab

[English](README.md)

這是一套把三種 AI 工作變得可檢查、可重跑、可交接的工具組：沿著完整資料路徑找出
agent 系統真正斷掉的位置、用兩個互不污染的視角複核投資研究，以及在生成影像前，
先把場景構想整理成經人確認的分鏡與鏡頭契約。

它不是 prompt 展示櫃。三個 clean-room Skill 都有白話輸入引導、專業工作流程、
機器可讀產物、確定性驗證器、合成失敗案例，以及清楚的人類決策邊界。

帶日期的 repo 與公開狀態請見
[`PUBLICATION_STATUS.md`](PUBLICATION_STATUS.md)。

## 三個 Skill 實際能做什麼

### 1. 找出系統到底斷在哪一段

[`agent-system-integration-audit`](skills/agent-system-integration-audit/SKILL.md)
會在指定的唯讀範圍內，先沿著真正的資料生產者、轉接層與使用端追完整路徑，再判定問題類別。
它會交付中立的偵測紀錄、綁定證據的稽核封包，以及仍未觀測到的風險；不會自行取得修復權限。

在這批凍結合成對照案例中，可供專業使用的稽核封包由 **0/3 → 2/3**；
真正找出語意缺陷的能力則維持 **3/3 → 3/3**。也就是說，它改善的是交付品質、
證據可追溯性與稽核規格，不是讓模型突然更會找錯。

### 2. 不讓一份很好看的報告跑得比來源更遠

[`dual-lens-investment-review`](skills/dual-lens-investment-review/SKILL.md)
把「這份報告能不能幫助決策」與「來源是否真的支持內容」分成兩個隔離的複核視角。
兩份結果都必須通過封閉格式與身分驗證，才能進入確定性的合併判定；重大來源問題可以直接擋下發布。

有效的雙視角交付由 **0/6 → 6/6**，合併判定由 **0/3 → 3/3**。
這輪沒有評分自由推理能力是否提升。它證明的是交付紀律、證據綁定、重大性判斷與複核治理，
不是投資績效，也不是交易建議。

### 3. 在開始生成之前，先讓每個鏡頭都能被檢查

[`ai-anime-production-director`](skills/ai-anime-production-director/SKILL.md)
會把導演意圖整理成有時間節點的分鏡、清楚的參考圖用途、人工核准紀錄與鏡頭契約。
如果連戲、動作或參考圖角色互相衝突，流程會停在人類決策關卡；不會默默授權生圖、生成影片或花費。

有效的分鏡／製作流程產物由 **0/2 → 2/2**。這輪沒有可用的盲測偏好結果，
也尚未證明最終成片品質。現有證據支持的是前期製作結構與遇錯停止的交接流程，
不是「最後動畫一定更好看」。

## 這些數字代表什麼

目前結果來自對 25 份既有執行收據所做的離線品質重評；沒有新增模型呼叫，也沒有刪除原本的失敗。
每個案例目前只有一組成對執行，因此它可以作為本機工程證據，不能包裝成具有統計強度的公開 benchmark。

精確的機器可讀結果在
[`evidence/benchmark-summary.json`](evidence/benchmark-summary.json)，白話解釋在
[`evidence/README.md`](evidence/README.md)。目前的宣稱關卡是
`EXPAND_BEFORE_PUBLIC_CLAIMS`。

這個套件尚未證明模型普遍變聰明、Skill B 的自由推理能力提升、最終成片品質提升、
投資績效、production 認證，或能跨所有模型與任務維持相同效果。

## 套件內容

- `skills/`：三個可分開安裝的 clean-room Skill。
- `scripts/`：組裝、證據與公開邊界檢查工具。
- `tests/`：契約、回歸、異常輸入、合成案例與整包測試。
- `evidence/`：去識別後的彙總結果與限制，不放原始模型對話。
- `provenance/`：公開來源紀錄、權利盤點與檔案 manifest。

## Verify locally（本機驗證）

在 repo 根目錄，照下面原樣連續跑兩次標準函式庫測試：

```sh
python3 -m unittest discover -s tests
python3 -m unittest discover -s tests
```

第二次不是誤植：它用來確認 Python 正常產生 bytecode cache 後，公開契約仍然全綠。
兩個指令都不需要加 `-B`。

## 權利與公開狀態

已拍板的 GitHub repo slug 是 `agent-skills-lab`。本套件依 evaluation-only
[`LICENSE`](LICENSE) 提供作品集檢視與評估；它不是開源專案，未經 Titus Lai 事前書面同意，
不得重用、修改或散布。

帶日期的 repo 與公開狀態 ledger 收在
[`PUBLICATION_STATUS.md`](PUBLICATION_STATUS.md)；之後由 owner 執行的可見性變更，
不會回寫或改造既有歷史 row。
