---
title: "AIエージェント9体で経営OSを構築した全記録【OpenClaw実践】"
emoji: "🤖"
type: "tech"
topics: ["data", "ses", "freelance", "claude", "ai"]
published: true
---

# AIエージェント9体で経営OSを構築した全記録【OpenClaw × Claude Code 実践レポート】

「社長業の8割はAIに任せられる」——この仮説を検証するために、2026年初頭から本格的にOpenClawを使ったAI経営OSの構築を始めた。

結論から言うと、**財務分析・市場調査・タスク管理・コンテンツ生成の4領域は完全に自動化できた**。SESエンジニアとして独立準備をしている人にとっても、このAI経営OSのアーキテクチャは直接応用できる部分が多い。

本記事では、OpenClawで9体のAIエージェントをどう設計・実装したか、技術的な設定の詳細と経営的な成果の両方を赤裸々に公開する。

---

## OpenClawとは何か——Claude Codeの拡張エコシステム

OpenClawは、Claude Codeのスキル・エージェント定義をYAMLで管理し、複数エージェントをオーケストレーションするフレームワークだ。`.claude/skills/`と`.claude/agents/`ディレクトリにMarkdownファイルを置くだけで、`/skill-name`コマンドとして呼び出せる。

```bash
# OpenClaw プロジェクト構造
.claude/
  skills/
    cfo.md          # 財務分析エージェント
    cto.md          # 技術戦略エージェント
    cmo.md          # マーケティングエージェント
    coo.md          # オペレーション管理
    ceo.md          # 統合意思決定
    research-scout.md  # 市場調査
    tasks.md        # タスク管理
    pl.md           # P&L分析
    dash.md         # ダッシュボード生成
  settings.json
  CLAUDE.md
```

Claude Code本体はAnthropicのモデルに対してAPI通信をするが、OpenClawはその上にドメイン特化の文脈・ツール権限・プロンプトテンプレートを乗せる中間層として機能する。

---

## 9体のエージェント構成と設計思想

### エージェント一覧

| エージェント名 | 役割 | 主なツール権限 |
|---|---|---|
| CEO | 経営判断の統合・優先度設定 | 全読み取り |
| CFO | 財務分析・P&L管理 | Read, Bash, WebFetch |
| CTO | 技術選定・アーキテクチャレビュー | Bash, Read, Grep |
| CMO | マーケティング戦略・SNS分析 | WebSearch, WebFetch |
| COO | オペレーション最適化 | Bash, Read |
| Research Scout | 市場調査・競合分析 | WebSearch, WebFetch, Read |
| Tasks Manager | タスク分解・進捗管理 | TaskCreate, TaskList, TaskUpdate |
| P&L Analyzer | 損益計算・予測モデル | Read, Bash |
| Dashboard | KPIビジュアライゼーション | Read, Write, Bash |

### 設計の核心：権限の最小化

最初に全エージェントに全権限を与えたら、AIが勝手にファイルを書き換えたりコマンドを実行しようとして大混乱した。教訓：**エージェントの権限は職責に対して最小限にする**。

Research Scoutは読み取りと検索のみ。財務系エージェントはファイル読み取りとBashのみ（書き込みは人間承認後）。この権限分離が安全な無人運用の前提になる。

---

## 実装：CFOエージェントの設定例

```markdown
# .claude/skills/cfo.md

---
name: cfo
description: |
  CFO（最高財務責任者）。P&L分析、キャッシュフロー管理、
  財務予測、コスト最適化提案を担当。
  数値は必ずソースを明記し、推定値は推定と明示する。
tools:
  - Read
  - Bash
  - WebFetch
permissions:
  allow:
    - "Read(*)"
    - "Bash(grep *)"
    - "Bash(cat *)"
    - "Bash(wc *)"
  deny:
    - "Write(*)"
    - "Edit(*)"
---

# CFO Agent Instructions

あなたは経験豊富なCFOです。以下の優先順位で行動します：

1. **データ確認優先**: 推測で答えず、必ずソースファイルを読んでから回答
2. **保守的見積もり**: 収益は控えめに、コストは多めに見積もる
3. **アクション提案**: 分析だけでなく、次の具体的なアクションを3つ提示

## 利用可能なデータソース
- `data/pl/` — 月次P&Lデータ（CSV）
- `data/subscriptions/` — サブスク収益データ
- `data/expenses/` — 経費データ

## 出力フォーマット
月次サマリーは以下の構造で出力：
- 売上: ¥X（前月比±Y%）
- 費用: ¥X（主要コスト：）  
- 営業利益: ¥X（利益率X%）
- 重点課題: 3点
- 推奨アクション: 3点
```

ポイントは`deny`セクション。CFOはあくまで読んで分析するだけで、ファイルの書き換えは人間がやる。AIを使いこなすコツは「何をさせないか」の設計だ。

---

## データ分析エージェントの実装：市場調査を自動化する

SESエンジニアがフリーランス独立準備をする際、**単価相場の調査**が最も時間のかかる作業の一つだ。これをResearch Scoutエージェントに任せている。

```bash
# Claude Codeでリサーチスカウトを起動
/openclaw-keiei-os:research-scout

# プロンプト例
「Pythonデータエンジニアのフリーランス単価相場を調査して。
2026年の最新データを使い、スキルセット別に整理して。」
```

エージェントは自動でWebSearchとWebFetchを組み合わせ、複数ソースから情報を収集・統合してくれる。重要なのは、**エージェント定義に「出典を必ず明記」と書いている**点だ。AIが作り話をするリスクを設計段階で抑制している。

### Research Scoutの内部処理フロー

```
1. WebSearch: キーワードで最新情報を検索
2. WebFetch: 上位3-5ソースの本文を取得
3. 情報統合: 矛盾する情報は「調査ごとに異なる」と明示
4. 出典付きサマリー: Markdown形式で整形出力
```

このフローを毎朝7時にcronで回して、`data/market-research/`に保存している。経営者として「昨日の市場動向」を朝イチで確認できる体制が整った。

---

## 技術スタック別 SES単価相場の分析アプローチ

SES単価相場の徹底比較をAIエージェントで自動化する場合、スクレイピング単体では精度が低い。私が採用したのは**三角測量アプローチ**だ。

### 三角測量による単価データ分析

```python
# data/analyze_market.py
# Research Scoutが収集したデータを集計するスクリプト

import json
import statistics
from pathlib import Path

def analyze_rate_data(tech_stack: str) -> dict:
    """
    複数ソースから収集した単価データを集計
    外れ値を除外した中央値を信頼できる相場として使用
    """
    data_dir = Path(f"data/market-research/{tech_stack}")
    all_rates = []
    
    for json_file in data_dir.glob("*.json"):
        with open(json_file) as f:
            data = json.load(f)
            rates = data.get("monthly_rates", [])
            all_rates.extend(rates)
    
    if not all_rates:
        return {"error": "データ不足"}
    
    # 外れ値除外（上下10%カット）
    sorted_rates = sorted(all_rates)
    trim = len(sorted_rates) // 10
    trimmed = sorted_rates[trim:-trim] if trim > 0 else sorted_rates
    
    return {
        "tech_stack": tech_stack,
        "median": statistics.median(trimmed),
        "mean": statistics.mean(trimmed),
        "min": min(trimmed),
        "max": max(trimmed),
        "sample_count": len(all_rates),
        "trimmed_count": len(trimmed)
    }
```

このスクリプトをCFOエージェントが定期的に実行し、`/cfo`コマンドで呼ぶと最新の市場分析が返ってくる。

---

## 経営OSとしての統合：CEOエージェントの設計

9体のエージェントを束ねるのがCEOエージェントだ。他エージェントの出力を読み込み、経営判断の優先度を設定する。

```markdown
# CEO エージェントのプロンプト骨格

あなたは経営者です。以下の情報源を参照して経営判断を行います：

## 参照データ
- CFOレポート: `data/reports/cfo_latest.md`
- 市場調査: `data/market-research/latest.md`  
- タスク状況: `tasks/todo.md`
- KPIダッシュボード: `data/kpi/current.json`

## 判断フレームワーク
1. 現金残高が3ヶ月分を切ったら収益施策を最優先
2. 主力事業の成長率が鈍化したら新規施策を検討
3. 全施策はインパクト×実行速度でスコアリング

## 禁止事項
- 数値なしの「頑張ります」系アドバイス
- 3ヶ月以上先の詳細計画（不確実性が高すぎる）
```

CEOエージェントを`/dash`コマンドのトリガーに設定して、毎朝の経営ダッシュボードを自動生成している。

---

## フリーランス独立準備にAI経営OSを使う実践例

SESエンジニアがフリーランス独立準備をする際、このAI経営OSのアーキテクチャは直接応用できる。

### 独立前に構築すべきAIエージェント3体

**1. 案件市場分析エージェント**
```bash
# Research Scoutをカスタマイズ
「レバテック・ギークスの公開案件データから、
自分のスキルセット（Python/データ分析/機械学習）に
マッチする案件の単価帯を週次で集計して」
```

**2. 財務シミュレーションエージェント**
```bash
# CFOエージェントへの問い合わせ例
「月額単価80万円でフリーランス転向した場合、
源泉徴収・社会保険・経費を考慮した手取りと、
損益分岐点になる稼働日数を計算して」
```

**3. スキルギャップ分析エージェント**
```bash
# CTOエージェントへの問い合わせ例  
「現在の案件市場でPython/データエンジニア系が求める
スキルスタックと、私の現スキルのギャップを分析して。
習得優先度をROIで並べて」
```

この3体を使い回すだけで、独立の意思決定に必要なデータ分析の8割はカバーできる。

---

## OpenClaw設定の実際：ハマったポイントと解決法

### ハマり1：エージェントが「前の会話」を覚えていない

**症状**: `/cfo`を呼ぶたびに「初めまして」状態になる  
**原因**: Claude Codeの各スキル呼び出しはステートレス  
**解決策**: 重要な文脈はMarkdownファイルに書き出し、エージェント定義でそのファイルを参照させる

```markdown
# CFOエージェントに追記
## 会社の基本情報
`company/profile.md`を必ず最初に読むこと。
このファイルに事業概要・KPI目標・過去の意思決定経緯が記録されている。
```

### ハマり2：WebSearchが古い情報を返す

**症状**: SES単価相場の調査で2024年のデータが出てくる  
**解決策**: プロンプトに日付制約を明示する

```markdown
## Research Scoutに追記
検索クエリには必ず「2026年」「最新」を含めること。
1年以上前のデータは「古いデータ」と明示して参考値として提示。
```

### ハマり3：macOS cronでclaudeコマンドが動かない

**症状**: launchdで設定したcronがサイレント失敗  
**原因**: launchdはPATHが通っていない、claude認証keepaliveが死ぬと全滅  
**解決策**: PM2で管理する

```bash
# PM2でcron代替
pm2 start ecosystem.config.js

# ecosystem.config.js
module.exports = {
  apps: [{
    name: 'morning-report',
    script: '/Users/apple/ses-content-automation/scripts/morning_report.sh',
    cron_restart: '0 7 * * *',
    watch: false,
    autorestart: false
  }]
}
```

launchdは無音停止するので、PM2の方が圧倒的に信頼性が高い。これはmacminiで無人運用する場合の鉄則だ。

---

## SES単価相場の徹底比較：AIが分析したデータの読み方

AIエージェントが収集したデータを「そのまま信じる」のは危険だ。徹底比較のフレームワークとして以下を使っている。

### 単価データの信頼性評価マトリクス

| データソース | 信頼度 | 特徴 |
|---|---|---|
| エージェント公開案件 | ★★★★★ | リアルタイム、条件明確 |
| フリーランス向け求人サイト | ★★★★☆ | 更新頻度高い |
| SNS・コミュニティ情報 | ★★★☆☆ | 体験談ベース、バイアスあり |
| 転職サイトの「年収目安」 | ★★☆☆☆ | 実態と乖離しやすい |
| AIが生成した「相場感」 | ★☆☆☆☆ | 幻覚リスク高、使用禁止 |

Research Scoutには「AIが相場を推測することを禁止」とエージェント定義に明記している。ソースURLが引用できないデータは出力しない設定だ。

---

## 経営的な成果：AI経営OS導入から半年

定量的な数値を出したいところだが、「AIのおかげで売上がX%増」という因果関係は証明できない。正直に言える成果は以下だ。

**確実に変わったこと：**
- 週次の経営レビューにかかる時間：4時間→45分（主にデータ収集・整形の自動化）
- 市場調査のタイムラグ：1週間→翌朝（cronで毎日自動収集）
- 「あの案件の単価どうだったっけ」という検索時間：消滅（全データがMarkdownで蓄積）
- フリーランス案件の意思決定スピード：大幅向上（CFOエージェントで即シミュレーション）

**変わらなかったこと：**
- 最終的な意思決定は人間がする
- 重要な交渉・関係構築はAIに任せられない
- 新規事業のアイデア出しはまだ人間の方が質が高い

AI経営OSは「考える」ツールではなく「調べる・整理する・計算する」の自動化ツールだ。この区分を最初から明確にしていたから、過度な期待からくる失望がなかった。

---

## OpenClaw導入のロードマップ：スモールスタートを推奨

9体同時に作ろうとすると確実に頓挫する。私が辿った順序：

**Week 1-2**: Research Scout1体だけ作る
→ 市場調査の自動化だけで十分価値を実感できる

**Week 3-4**: CFOを追加
→ 月次P&Lを自動集計・分析する体験で一気に理解が深まる

**Month 2**: COO・Tasks Managerを追加
→ オペレーション管理が自動化され、本業に集中できる時間が増える

**Month 3以降**: CEO・CMO・CTOなどを段階的に追加

SESエンジニアの独立準備に当てはめると：**まず案件市場分析エージェント1体だけ作る**。これで単価相場の把握が自動化されれば、独立判断に必要なデータが毎週手に入る。

---

## まとめ：AI経営OSは「意思決定の高速化装置」

OpenClawで9体のAIエージェントを構築して分かったことは、AIは「スーパーな分析師」ではなく「疲れない情報収集者」だということだ。

人間がやっていた「調べる・整理する・計算する」の繰り返し作業をAIが担い、人間は「判断する・実行する・関係を築く」に集中できる。

SES単価相場のデータ分析、フリーランス独立準備の財務シミュレーション、市場の徹底比較——これらは全てAIエージェントに任せられる作業だ。

重要なのは「完璧なAIを作ろうとしない」こと。シンプルなエージェント1体から始めて、実際に使いながら改善していく。それが半年後に9体の経営OSに育った唯一の理由だ。


## 関連記事

- [Claude Code毎日使い倒して気づいた実践Tips集【2026年版】SESエンジニアのフリーランス転身にも効く](https://qiita.com/sescore/items/88f8ce268734e761bcac)
- [SESエンジニアがフリーランス独立前に絶対確認すべき税務・節税の全知識【2026年最新版】](https://qiita.com/sescore/items/508398300d7d26e26a40)
- [OpenClaw×Claude Code連携実践録——SES脱出を加速するAI開発OSの全貌2026](https://qiita.com/sescore/items/919fc2c210407303f471)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/d0457d54d5a53495b286

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://radineer.asia/freelance/register?utm_source=zenn&utm_medium=article&utm_campaign=ai%E3%82%A8%E3%83%BC%E3%82%B8%E3%82%A7%E3%83%B3%E3%83%889%E4%BD%93%E3%81%A7%E7%B5%8C%E5%96%B6os%E3%82%92%E6%A7%8B%E7%AF%89%E3%81%97%E3%81%9F%E5%85%A8%E8%A8%98%E9%8C%B2-openclaw%E5%AE%9F%E8%B7%B5)**

