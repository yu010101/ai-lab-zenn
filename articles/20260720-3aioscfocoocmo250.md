---
title: "3人会社にAI経営OSを実装した全記録——CFO/COO/CMOエージェントの作り方と月商250万円の変化"
emoji: "🤖"
type: "tech"
topics: ["ai", "agent", "claude", "freelance", "data"]
published: true
---

## はじめに：SES 1年目の転職衝動から始まった「経営の孤独」

SES業界に入ったエンジニアの多くが、入社1年以内に転職を真剣に考える。私もその一人だった。**SES 1年目**のうちに転職活動をはじめ、最終的にフリーランスへ転向した。当時の単価相場は月60〜80万円。スキルと営業力次第で上振れる市場だった。

その後、フリーランスを2年経験してから法人化し、現在は3人体制で月商約250万円の会社を運営している。

この記事の主役は **SES転職の話ではない**。「3人でも経営できるか」という問いに対して、AIエージェントで経営機能を補完した実録だ。SES からフリーランス、そして法人化という流れを経験した私が、実際にAI経営OSを構築した過程を具体的に共有する。

---

## AI経営OSとは何か：概念から実装まで

「AI経営OS」という言葉は私が勝手に使っている造語だ。正確に言うと、**経営管理の各機能（財務・オペレーション・マーケティング・意思決定）をAIエージェントに分担させる仕組み**のことを指している。

大企業にはCFO（最高財務責任者）、COO（最高執行責任者）、CMO（最高マーケティング責任者）がいる。3人会社にはいない。だから作った。

```
AI経営OS の構成
├── CFOエージェント（財務・PL分析）
├── COOエージェント（タスク・プロセス管理）
├── CMOエージェント（集客・コンテンツ）
├── CEOダッシュボード（統合意思決定支援）
└── 各種データソース（会計・CRM・analytics）
```

技術的には Claude Code + Claude API + 自社ツール OpenClaw の組み合わせで実装している。

---

## 技術スタック

実装で使っているツールを先に公開する。

| レイヤー | 使用ツール |
|---------|----------|
| AIエージェント基盤 | Claude Code (Sonnet 4.6) |
| エージェントオーケストレーション | OpenClaw（自社内製） |
| 会計データソース | freee API |
| データ分析・可視化 | Neon (PostgreSQL) + Metabase |
| スケジュール実行 | PM2 (cron) |
| コード管理 | GitHub |

**なぜ OpenAI ではなく Claude か？**

コンテキストウィンドウの大きさとツール使用の安定性が理由だ。エージェントが長い財務レポートを読んで分析する場面では、200Kトークンのウィンドウが実用的に効いてくる。複数ファイルを横断して読み書きする Claude Code の能力は、経営OSのような「複数データソースを統合する」用途に特に向いている。

---

## CFOエージェント：財務分析の自動化

### アーキテクチャ

CFOエージェントは毎月5日に自動起動し、前月分の損益計算書を取得・分析してSlackに届ける。

```bash
# PM2で管理しているcronジョブ（ecosystem.config.js の一部）
{
  name: 'cfo-agent-monthly',
  script: './agents/cfo/run.sh',
  cron_restart: '0 9 5 * *',
  watch: false,
  autorestart: false,
}
```

```bash
#!/bin/bash
# agents/cfo/run.sh
set -e

# freee APIからPL取得
node scripts/fetch-freee-pl.js > /tmp/pl_current.json

# Claude Code でPL分析（macOSにはtimeoutコマンドがないのでgtimeoutを使う）
gtimeout 120 claude --print "$(cat prompts/cfo-analysis.md)" \
  --file /tmp/pl_current.json \
  >> logs/cfo-reports/$(date +%Y-%m).md

# Slack通知
node scripts/notify-slack.js --file logs/cfo-reports/$(date +%Y-%m).md
```

### プロンプト設計

`prompts/cfo-analysis.md` の核心部分はこんな構造にしている。

```markdown
あなたはSaaSスタートアップ専門のCFOです。
添付のP/Lデータを分析し、以下を出力してください。

## 分析項目
1. 前月比の売上・費用変動（金額・率）
2. 異常値の検出（±20%以上の変動）
3. キャッシュフロー上の警告
4. 来月の財務予測（保守的シナリオ）
5. CFOとして代表に伝えるべき1つのアクション

## 出力フォーマット
- 数値は万円単位
- 専門用語は使わない（代表は財務の素人）
- 5分で読める分量
```

### 実際の効果と注意点

月次の帳簿確認と分析に、以前は丸1日かかっていた。今は30分で確認できる形式でSlackに届く。

ただし注意点がある。**AIが出した数値を鵜呑みにしてはいけない。** freee APIのデータ取得タイミングや仕訳ミスを拾わずに分析してくることがある。CFOエージェントはあくまで「草稿」として使い、最終確認は人間がやる。これは原則として変えていない。

---

## COOエージェント：オペレーション管理

### 週次タスクレビューの自動化

COOエージェントは毎週月曜朝8時に起動し、GitHub Issues と Notion のタスクを集約してレビューレポートを生成する。

```javascript
// agents/coo/weekly-review.js
const Anthropic = require('@anthropic-ai/sdk');
const { fetchGitHubIssues } = require('./sources/github');
const { fetchNotionTasks } = require('./sources/notion');

async function runWeeklyReview() {
  const [githubIssues, notionTasks] = await Promise.all([
    fetchGitHubIssues({ state: 'open', days: 7 }),
    fetchNotionTasks({ status: ['In Progress', 'Blocked'] })
  ]);

  const client = new Anthropic();

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    messages: [{
      role: 'user',
      content: `
        以下のタスクデータを分析し、COOレポートを作成してください。

        GitHub Issues: ${JSON.stringify(githubIssues)}
        Notion Tasks: ${JSON.stringify(notionTasks)}

        分析してほしいこと：
        1. ブロック中タスクとその原因推定
        2. 今週の優先度TOP3
        3. チームの作業負荷バランス
        4. プロセス上の改善提案
      `
    }]
  });

  return response.content[0].text;
}
```

### データソース統一のための中間DB設計

一番時間がかかったのはデータ収集の部分だった。GitHub・Notion・freee・Google AnalyticsそれぞれのAPIの仕様が異なり、Notion APIは日本語コンテンツで稀に文字化けが起きる（2026年現在も発生する）。

**解決策：** 全データソースから取得したデータを一度 Neon (PostgreSQL) に正規化して格納し、エージェントはそこから読む設計にした。

```sql
-- データ正規化テーブル
CREATE TABLE business_events (
  id          SERIAL PRIMARY KEY,
  source      VARCHAR(50) NOT NULL,  -- 'github', 'notion', 'freee'
  event_type  VARCHAR(100),
  title       TEXT,
  status      VARCHAR(50),
  amount      DECIMAL(12, 2),
  created_at  TIMESTAMPTZ,
  raw_data    JSONB
);

CREATE INDEX idx_business_events_source_date
  ON business_events (source, created_at DESC);
```

この設計にしてから、エージェントへのデータ供給が安定した。

---

## CMOエージェント：マーケティングとデータ分析の自動化

### コンテンツ生成パイプライン

私が一番力を入れたのがCMOエージェントだ。月商250万円を維持するための集客を、3人で回すには自動化が必須だった。

```
CMOエージェントのパイプライン

[トレンド収集]
    ↓
[キーワードデータ分析]
    ↓
[記事ブリーフ生成]
    ↓
[下書き生成]
    ↓
[人間レビュー] ← ここで必ず人間が入る
    ↓
[公開]
```

**重要：自動公開はしていない。**

生成は自動化しているが、公開は必ず人間がレビューする。SNSへの連投は最低15分間隔を厳守している。

### Google Search Consoleデータ分析による記事選定

どの記事を書くかの判断に、Google Search Console のデータ分析を活用している。「インプレッションは多いがCTRが低いキーワード」＝すでに検索されているが上位表示できていないチャンスキーワードを自動検出する。

```python
# scripts/gsc-opportunity-finder.py
from googleapiclient.discovery import build
import pandas as pd
from datetime import date, timedelta

def find_quick_wins(service, site_url, days=90):
    """
    インプレッション多 & CTR低のキーワードを発見する
    """
    request = {
        'startDate': (date.today() - timedelta(days=days)).isoformat(),
        'endDate': date.today().isoformat(),
        'dimensions': ['query'],
        'rowLimit': 1000
    }

    response = service.searchanalytics().query(
        siteUrl=site_url, body=request
    ).execute()

    df = pd.DataFrame(response.get('rows', []))
    df['query'] = df['keys'].apply(lambda x: x[0])
    df['impressions'] = df['impressions'].astype(int)
    df['ctr'] = df['ctr'].astype(float)

    # インプレッション > 100 かつ CTR < 5% のキーワード
    quick_wins = df[
        (df['impressions'] > 100) &
        (df['ctr'] < 0.05)
    ].sort_values('impressions', ascending=False)

    return quick_wins.head(20)
```

このスクリプトで抽出したキーワードリストをCMOエージェントに渡し、記事ブリーフを自動生成する。単価相場や市場動向に関するキーワードも、このデータ分析から自動的に発掘されてくる。

---

## CEOダッシュボード：意思決定支援の統合

3つのエージェント（CFO/COO/CMO）のレポートを統合して、「今週の経営判断に必要な情報」をまとめるのがCEOエージェントの役割だ。

```markdown
# CEOプロンプトの構造

以下の3つのレポートを統合し、代表が今週判断すべき事項を
3点に絞って提示してください。

## CFOレポート（財務）
{cfo_report}

## COOレポート（オペレーション）
{coo_report}

## CMOレポート（マーケティング）
{cmo_report}

## 出力形式
### 今週の経営判断TOP3
1. [判断事項] → [推奨アクション] → [理由]
2. ...
3. ...

### 見逃せないリスク
- ...

### 来週の注目ポイント
- ...
```

このフォーマットで生成されたサマリーを毎週月曜の朝に受け取る。判断の拠り所が変わった実感がある。

---

## つまずいたポイント3選（正直に語る）

### ①「完成」のラインが見えない問題

AIエージェントは永遠に改善できる。プロンプトを変えれば出力が変わり、データソースを増やせばより正確になる。これが罠で、「もっと良くできる」と感じてリリースが遅れた。

**解決策：** 「MVPを2週間で出す」というルールを作った。まず動く状態を作り、運用しながら改善する。完璧主義はAIエージェント開発の敵だ。

### ②LLMの出力が安定しない

同じプロンプトでも、日によって出力の質が変わる。財務分析で「異常値」として検出するものが変わったりする。

**解決策：** 構造化出力（Structured Output）を使う。JSONスキーマを定義して、エージェントが必ず決まった形式で返すようにした。

```javascript
const response = await client.messages.create({
  model: 'claude-sonnet-4-6',
  max_tokens: 2048,
  tools: [{
    name: 'financial_report',
    description: '財務分析レポートを構造化して出力する',
    input_schema: {
      type: 'object',
      properties: {
        revenue_change_pct: { type: 'number' },
        cost_change_pct:    { type: 'number' },
        alerts: {
          type: 'array',
          items: { type: 'string' }
        },
        recommendation: { type: 'string' }
      },
      required: [
        'revenue_change_pct',
        'cost_change_pct',
        'alerts',
        'recommendation'
      ]
    }
  }],
  tool_choice: { type: 'tool', name: 'financial_report' }
});
```

### ③エラーハンドリングの軽視

初期は「エラーが起きたらSlackに通知する」だけだった。実際に運用すると、freee APIの一時障害でCFOエージェントが途中で落ち、不完全なレポートが届いた。

**解決策：** リトライロジックとフォールバックを実装した。APIエラーは最大3回リトライ、それでも失敗した場合は「データ取得失敗」として明示的に通知する。

```javascript
async function fetchWithRetry(fetchFn, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fetchFn();
    } catch (error) {
      if (attempt === maxRetries) {
        throw new Error(
          `Failed after ${maxRetries} attempts: ${error.message}`
        );
      }
      // exponential backoff
      await new Promise(r =>
        setTimeout(r, 1000 * Math.pow(2, attempt))
      );
    }
  }
}
```

---

## SES・フリーランス出身者がAI経営OSを作るべき理由

### 「一人で全部やる大変さ」の正体

SES 1年目で転職を考え、実際に SES からフリーランスへ転向した私が最初に実感したのは、**営業・経理・確定申告・保険手続きを全部一人でやる大変さ**だった。

フリーランスの単価相場がいくら高くても、これらの管理コストが高ければ手取りは想像より下がる。特に確定申告の時期に帳簿整理で1週間取られる経験をすると、「これを自動化できれば」と強く思う。

### 確定申告・節税の補助自動化

freeeを使って申告書を作っているが、「何が経費になるか」「何が節税につながるか」の知識が最初はなかった。

今はCFOエージェントが毎月の帳簿を確認し、「この費用は按分計算が必要です」「青色申告特別控除の要件を確認してください」といった提案を月次で出す。最終的な税務判断は税理士に確認するが、**「何を聞けばいいか」を整理する段階でAIは実用的**に機能する。

コードを書けるエンジニアなら、このパイプラインを構築するコストは低い。フリーランスになったばかりの人ほど、早めに仕組み化することを勧める。

---

## データ分析が変えた意思決定：Before / After

### Before（AI経営OS導入前）

| 業務 | 状況 |
|-----|------|
| 月次PL確認 | 毎月15日頃に手作業で確認、半日〜1日消費 |
| 記事パフォーマンス把握 | GSCを月1回手動確認 |
| タスク状況の把握 | Slackで口頭確認 |
| 意思決定の根拠 | 「なんとなくこう思う」が多かった |

### After（導入後）

| 業務 | 状況 |
|-----|------|
| 月次PL確認 | 5日に自動レポートがSlackに届く |
| 記事パフォーマンス把握 | 週次でデータ分析結果が届く |
| タスク状況の把握 | 週次COOレポートで可視化 |
| 意思決定の根拠 | データに基づく推奨アクション付き |

数値で表しにくい変化もある。「判断するのに必要な情報がない」状態で意思決定することが大幅に減った。これが一番大きい。

---

## 2026年7月現在：次に目指すもの

AI経営OSを本格稼働させて半年が経つ。現在取り組んでいる改善は以下の3点だ。

1. **エージェント間の連携強化**：CFOとCOOが情報を共有し、「財務状況を踏まえたリソース配分提案」ができるようにする
2. **予測モデルの精度向上**：過去データの蓄積が増えてきたので、翌月の売上予測の精度を上げたい
3. **クライアントレポートの自動化**：COOエージェントの成果物を、クライアント向けレポートに自動変換する

3人でも、AIを使えば10人分の経営情報を処理できる時代になっている。SESからフリーランスへ、そして法人化という道を歩んできた経験から言えることは、「経営管理の重さ」を恐れなくていいということだ。AIがそこをカバーできる。

---

## まとめ

- **AI経営OS**＝CFO/COO/CMO/CEOエージェントを構築し、経営管理を補完する仕組み
- **技術スタック**：Claude Code + Claude API + freee API + Neon + PM2
- **つまずきポイント**：完成基準の曖昧さ・LLM出力の不安定さ・エラーハンドリング不足
- **実際の効果**：月次財務確認の工数削減、データ分析に基づく意思決定の質向上
- **SESからフリーランスへ**転向後の「一人で全部やる大変さ」をAIで解決した
- 架空の数値は使わず、実運用から得た知見のみを共有している

コードを書けるエンジニアほど、この仕組みを作るコストは低い。自社・個人の経営に取り入れてみてほしい。


## 関連記事

- [2026年最新｜OpenClawで経営OSを自作した話——9体のAIエージェントが会社を回す](https://qiita.com/sescore/items/1b0f47d7d3885a38995e)
- [Claude Code毎日使い録：SESエンジニアがデータ分析を自動化してフリーランス転向を考えた話](https://qiita.com/sescore/items/25c7b6f65e6722115c32)
- [SESつらいエンジニアが2026年にフリーランスへ転身する最短ルート【データ分析×AI活用】](https://qiita.com/sescore/items/0874fd5363e1fd43afd4)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/0a54bf1232c0b290cbf4

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://radineer.asia/freelance/register?utm_source=zenn&utm_medium=article&utm_campaign=3%E4%BA%BA%E4%BC%9A%E7%A4%BE%E3%81%ABai%E7%B5%8C%E5%96%B6os%E3%82%92%E5%AE%9F%E8%A3%85%E3%81%97%E3%81%9F%E5%85%A8%E8%A8%98%E9%8C%B2-cfo-coo-cmo%E3%82%A8%E3%83%BC%E3%82%B8%E3%82%A7%E3%83%B3%E3%83%88%E3%81%AE%E4%BD%9C%E3%82%8A%E6%96%B9%E3%81%A8%E6%9C%88%E5%95%86250%E4%B8%87%E5%86%86%E3%81%AE%E5%A4%89%E5%8C%96)**

