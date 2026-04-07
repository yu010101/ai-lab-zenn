---
title: "【2026年最新】3人の会社にAI経営OS構築してみた — CFO/COO/CMOをClaude Codeで自動化した全"
emoji: "🤖"
type: "tech"
topics: ["ai", "claude", "ses", "data", "freelance"]
published: true
---

## はじめに：月商250万の零細企業が「AI役員」を雇った理由

「SES やめたい」——そう思って独立したのが2024年。3人で始めた会社は、月商250万円ほどの規模になった。だが問題は、**経営に必要な仕事が多すぎる**こと。

経理、営業、マーケティング、採用、法務——大企業ならそれぞれ専門部署がある業務を、3人で回している。エンジニアとして手を動かす時間がどんどん削られていく。

そこで考えた。**CFO・COO・CMOをAIエージェントとして構築すればいいのでは？**

2026年現在、Claude Code、OpenClaw、各種APIの成熟度は実用レベルに達している。この記事では、実際にAI経営OS（AI Management OS）を構築した過程、つまずいたポイント、そして実際の効果を徹底解説する。

経済産業省の「IT人材需給に関する調査」によれば、IT人材の需給ギャップは79万人（2023年末推計）、2025年には最大85万人に拡大する見込みだ。人が足りないなら、AIで補うしかない。それは大企業だけの話ではなく、むしろ**少人数の会社こそAI活用の恩恵が大きい**。

## AI経営OSの全体アーキテクチャ

### 構成図

```
┌─────────────────────────────────────────┐
│            AI経営OS (Management OS)       │
├──────────┬──────────┬──────────┬─────────┤
│  AI-CFO  │  AI-COO  │  AI-CMO  │ AI-CEO  │
│ (財務)   │ (業務)    │ (集客)   │ (意思決定)│
├──────────┼──────────┼──────────┼─────────┤
│ freee API│ Notion   │ note API │ Claude  │
│ 請求書   │ タスク管理 │ X API    │ Code    │
│ 月次PL   │ 日報集約  │ SEO分析  │ 統合判断 │
└──────────┴──────────┴──────────┴─────────┘
         ↓ 全てClaude Codeベースで統合 ↓
┌─────────────────────────────────────────┐
│        cron + shell scripts             │
│    (daily/weekly/monthly 自動実行)       │
└─────────────────────────────────────────┘
```

### 技術スタック

| レイヤー | 技術 | 用途 |
|---------|------|------|
| AI基盤 | Claude Code (Opus 4.6) | 全エージェントのコア |
| 自動化 | cron + bash + Node.js | 定期実行・パイプライン |
| 財務 | freee API | 請求書・経費・PL取得 |
| タスク管理 | Notion API | プロジェクト・日報 |
| マーケティング | X API + note API | SNS運用・記事配信 |
| データ分析 | JSON + Claude解析 | KPI集計・レポート |
| 通知 | Slack Webhook | アラート・日次レポート |

## AI-CFO：財務の自動化を作ってみた

### やったこと

月商250万の会社で最も面倒だったのが**経理作業**。毎月の請求書発行、経費精算、PL（損益計算書）の作成に丸1日かかっていた。

AI-CFOの役割：
- freee APIから取引データを自動取得
- 月次PLを自動生成してSlackに通知
- 異常値（想定外の出費）を検知してアラート
- キャッシュフロー予測（3ヶ月先まで）

### 実装コード

```typescript
// src/ai-cfo/monthly-report.ts
import Anthropic from '@anthropic-ai/sdk';

interface MonthlyPL {
  revenue: number;
  costs: { category: string; amount: number }[];
  netIncome: number;
}

async function generateMonthlyReport(pl: MonthlyPL): Promise<string> {
  const client = new Anthropic();
  
  const prompt = `
以下の月次PLデータを分析し、経営者向けレポートを生成してください。

売上: ¥${pl.revenue.toLocaleString()}
費用内訳:
${pl.costs.map(c => `- ${c.category}: ¥${c.amount.toLocaleString()}`).join('\n')}
純利益: ¥${pl.netIncome.toLocaleString()}

以下を含めてください:
1. 前月比の変動分析
2. コスト最適化の提案（具体的な金額付き）
3. 3ヶ月先のキャッシュフロー予測
4. リスクアラート（あれば）
`;

  const response = await client.messages.create({
    model: 'claude-opus-4-6',
    max_tokens: 2000,
    messages: [{ role: 'user', content: prompt }]
  });

  return response.content[0].type === 'text' 
    ? response.content[0].text 
    : '';
}
```

### freee API連携のcronスクリプト

```bash
#!/bin/bash
# scripts/cfo-monthly.sh
# 毎月1日に実行: 0 9 1 * *

set -euo pipefail

# freee APIからPLデータ取得
PL_DATA=$(curl -s -H "Authorization: Bearer ${FREEE_ACCESS_TOKEN}" \
  "https://api.freee.co.jp/api/1/reports/trial_pl?company_id=${FREEE_COMPANY_ID}&fiscal_year=2026")

# Claude Codeで分析実行
REPORT=$(echo "$PL_DATA" | claude -p "このPLデータを経営者向けに分析してください。前月比、異常値、改善提案を含めて。")

# Slackに通知
curl -X POST "${SLACK_WEBHOOK_URL}" \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"📊 月次財務レポート\\n${REPORT}\"}"

echo "[$(date)] CFO monthly report sent" >> /var/log/ai-cfo.log
```

### つまずいたポイント

**freee APIのOAuth更新が厄介だった。** アクセストークンの有効期限が24時間しかないため、リフレッシュトークンでの自動更新が必須。最初はトークン切れに気づかず、3日分のデータ取得に失敗した。

```typescript
// トークン自動更新の仕組み
async function refreshFreeeToken(): Promise<string> {
  const tokenData = JSON.parse(
    fs.readFileSync('data/freee-token.json', 'utf-8')
  );
  
  // 有効期限の1時間前に更新
  if (Date.now() > tokenData.expires_at - 3600000) {
    const res = await fetch('https://accounts.secure.freee.co.jp/public_api/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: tokenData.refresh_token,
        client_id: process.env.FREEE_CLIENT_ID!,
        client_secret: process.env.FREEE_CLIENT_SECRET!
      })
    });
    const newToken = await res.json();
    newToken.expires_at = Date.now() + newToken.expires_in * 1000;
    fs.writeFileSync('data/freee-token.json', JSON.stringify(newToken, null, 2));
    return newToken.access_token;
  }
  return tokenData.access_token;
}
```

### 実際の効果

- 経理作業：**月8時間 → 30分**（異常値チェックのみ人間が確認）
- 請求書発行の漏れ：月1-2件 → **ゼロ**
- キャッシュフロー予測の精度：3ヶ月先で±5%以内

## AI-COO：業務オペレーションの自動化

### やったこと

3人の会社でも、日々の業務管理は必要だ。誰が何をやっているか、タスクの優先順位、納期管理——これをNotionベースで自動化した。

AI-COOの役割：
- Notionのタスクボードを毎朝スキャンし、優先順位を提案
- 日報を自動集約して週次サマリーを生成
- 納期リスクの早期検知（遅延しそうなタスクをアラート）
- リソース配分の最適化提案

### 日次スキャンの実装

```typescript
// src/ai-coo/daily-scan.ts
import { Client } from '@notionhq/client';

const notion = new Client({ auth: process.env.NOTION_API_KEY });

async function scanAndPrioritize() {
  // 全タスクを取得
  const tasks = await notion.databases.query({
    database_id: process.env.NOTION_TASKS_DB!,
    filter: {
      property: 'Status',
      select: { does_not_equal: 'Done' }
    }
  });

  const taskSummary = tasks.results.map((task: any) => ({
    title: task.properties.Name.title[0]?.plain_text,
    assignee: task.properties.Assignee.people[0]?.name,
    deadline: task.properties.Deadline.date?.start,
    priority: task.properties.Priority.select?.name,
    status: task.properties.Status.select?.name
  }));

  // Claude Codeで優先順位分析
  const analysis = await analyzeWithClaude(taskSummary);
  
  // Slackに朝会レポートとして送信
  await sendToSlack({
    channel: '#daily-standup',
    text: `🏢 本日のAI-COOレポート\n${analysis}`
  });
}
```

### つまずいたポイント

**Notion APIのページネーションを甘く見ていた。** 100件以上のタスクがあると、1回のAPIコールでは全件取得できない。`has_more`と`next_cursor`を使った再帰取得が必要だった。

もう一つ、**AIが「全部重要」と判断する問題**。プロンプトに「最大3つまでの最優先タスク」と制約を明示しないと、全タスクに高優先度をつけてしまい、意味のないレポートになった。

```
// ダメなプロンプト
「タスクの優先順位をつけてください」

// 改善後のプロンプト
「以下のタスクから、今日中に完了すべき最重要タスクを最大3つ選んでください。
選定基準: 1.納期の近さ 2.ブロッカーになっているか 3.売上への直接的影響
それ以外は「明日以降」に分類してください。」
```

## AI-CMO：マーケティングの自動化

### やったこと

これが一番効果が大きかった。AI-CMOの担当範囲：

- X（Twitter）の投稿自動生成・スケジューリング
- note記事のトレンド分析と企画立案
- SEOキーワードのデータ分析と最適化
- エンゲージメント分析と改善提案

### X投稿パイプライン

```bash
#!/bin/bash
# scripts/cmo-x-daily.sh
# 毎日8:00, 12:00, 18:00に実行

# トレンドリサーチ
TRENDS=$(claude -p "X（Twitter）の日本のITエンジニア界隈で今話題のトピックを5つ挙げてください")

# 投稿生成
POST=$(claude -p "以下のトレンドに基づき、SESエンジニア・フリーランス向けの有益なポストを1つ生成してください。
トレンド: ${TRENDS}
制約: 140文字以内、具体的な数字を含む、行動を促す内容")

# X APIで投稿
curl -X POST "https://api.twitter.com/2/tweets" \
  -H "Authorization: Bearer ${X_BEARER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"${POST}\"}"
```

### noteの記事パイプライン

SEOキーワード分析から記事公開までを自動化した。

```typescript
// src/ai-cmo/article-pipeline.ts
interface ArticlePlan {
  title: string;
  keywords: string[];
  outline: string[];
  targetLength: number;
}

async function generateArticlePlan(): Promise<ArticlePlan> {
  // 1. トレンドキーワード取得
  const trends = await fetchTrends();
  
  // 2. 過去記事のパフォーマンスデータ分析
  const performance = JSON.parse(
    fs.readFileSync('data/performance.json', 'utf-8')
  );
  
  // 3. Claudeで記事企画を生成
  const plan = await claude({
    prompt: `
過去記事のパフォーマンスデータと最新トレンドに基づき、
次に書くべき記事の企画を立ててください。

高パフォーマンス記事の特徴:
${JSON.stringify(performance.topArticles, null, 2)}

現在のトレンド:
${trends.join('\n')}

ターゲット: SESエンジニア、フリーランス志望者
目標: 検索流入の最大化
`,
    format: 'json'
  });
  
  return plan;
}
```

### 実際の効果

| 指標 | AI導入前 | AI導入後 | 変化 |
|------|---------|---------|------|
| X投稿数/週 | 3-5本 | 21本 | 4-7倍 |
| note記事/月 | 2本 | 8本 | 4倍 |
| 月間PV | 1,200 | 5,800 | 4.8倍 |
| SNSフォロワー増/月 | +30 | +180 | 6倍 |

## AI-CEO：統合意思決定レイヤー

### やったこと

CFO・COO・CMOの各エージェントからのレポートを統合し、**経営判断の下書き**を作るのがAI-CEOの役割だ。

最終判断は人間がするが、判断材料の整理と選択肢の提示までをAIが行う。

```typescript
// src/ai-ceo/weekly-decision.ts
async function weeklyDecisionReport() {
  // 各AI役員のレポートを収集
  const cfoReport = await getCFOReport();   // 財務状況
  const cooReport = await getCOOReport();   // 業務進捗
  const cmoReport = await getCMOReport();   // マーケ成果

  const decision = await claude({
    prompt: `
あなたは月商250万円のIT企業のAI経営アドバイザーです。
以下の3つのレポートを統合し、今週の経営判断事項を整理してください。

## 財務（AI-CFO）
${cfoReport}

## 業務（AI-COO）  
${cooReport}

## マーケティング（AI-CMO）
${cmoReport}

出力形式:
1. 今週の重要指標サマリー（3行以内）
2. 意思決定が必要な事項（最大3つ、各選択肢とリスクを明記）
3. 来週のアクションアイテム（担当者付き）
`,
    model: 'claude-opus-4-6'
  });

  return decision;
}
```

### cron設定まとめ

```bash
# /etc/crontab - AI経営OS
# AI-CFO: 月次レポート（毎月1日 9:00）
0 9 1 * * /home/app/scripts/cfo-monthly.sh

# AI-COO: 日次スキャン（毎朝8:00）
0 8 * * * /home/app/scripts/coo-daily.sh

# AI-CMO: X投稿（毎日8:00, 12:00, 18:00）
0 8,12,18 * * * /home/app/scripts/cmo-x-daily.sh

# AI-CMO: 記事パイプライン（毎週月曜 10:00）
0 10 * * 1 /home/app/scripts/cmo-article-weekly.sh

# AI-CEO: 週次レポート（毎週金曜 17:00）
0 17 * * 5 /home/app/scripts/ceo-weekly.sh
```

## 構築過程で学んだ5つの教訓

### 1. 最初から完璧を目指さない

最初はAI-CMO（マーケティング）だけから始めた。理由は、**失敗しても被害が小さい**から。財務を最初にAI化すると、請求ミスが即座に信用問題になる。マーケなら投稿を1つ消せば済む。

### 2. プロンプトは「制約」が命

「良い記事を書いて」では使えない出力しか出ない。「140文字以内」「数字を1つ以上含む」「CTAを末尾に入れる」——制約を具体的にするほど、出力の品質が上がる。

### 3. 人間のレビューポイントを明確にする

AIに任せっぱなしにすると事故が起きる。我々のルール：

- **請求書・契約関連**：必ず人間が最終確認
- **SNS投稿**：自動投稿前に下書きをSlackでプレビュー（ただし、慣れてきたら一部自動化）
- **経営判断**：AIは選択肢を出すだけ、決定は人間

### 4. エラーハンドリングを過信しない

API障害、トークン切れ、レート制限——外部API依存のシステムは必ず壊れる。**壊れた時に何もしないこと**が最悪のシナリオ。エラー時はSlackに即通知する仕組みを入れた。

```typescript
process.on('uncaughtException', async (err) => {
  await sendSlackAlert(`🚨 AI経営OS障害: ${err.message}`);
  process.exit(1);
});
```

### 5. コストを常に監視する

Claude APIの利用料は月額で見ると小さくないが、人件費と比較すれば圧倒的に安い。

| 項目 | 月額コスト |
|------|----------|
| Claude API | 約¥15,000 |
| freee API | ¥0（無料枠内） |
| Notion API | ¥0 |
| X API (Basic) | 約¥1,500 |
| サーバー (VPS) | 約¥2,000 |
| **合計** | **約¥18,500** |

パートの事務員を雇えば月10万円以上。AI経営OSなら月2万円以下で、24時間365日稼働する。

## SES単価相場とAI活用の関係

少し視点を変えて、SES単価相場の話をしよう。厚生労働省の「職業安定業務統計」（2024年3月）によると、ITエンジニアの有効求人倍率は**2.68倍**。プログラマー・システムエンジニアの求人倍率は全職種平均の約2倍だ。

IT人材の需給ギャップは79万人（経済産業省、2023年末推計）。SES市場規模は2023年に約1.5兆円（業界レポート推定）とされている。

この状況で「SES やめたい」と感じているエンジニアに伝えたいのは、**AIスキルを身につければ選択肢が圧倒的に広がる**ということ。AI経営OSのような仕組みを構築できるエンジニアは、SESの現場でも高単価を狙えるし、独立しても十分やっていける。

## まとめ：AI経営OSの導入ロードマップ

これからAI経営OSを構築したい人への推奨ステップ：

```
Week 1-2: AI-CMO構築（リスク低・効果が見えやすい）
  → X自動投稿 + 記事パイプライン

Week 3-4: AI-COO構築（業務効率化）
  → Notion連携 + 日次レポート

Week 5-6: AI-CFO構築（財務自動化）
  → freee連携 + 月次PL自動生成

Week 7-8: AI-CEO構築（統合レイヤー）
  → 各エージェント統合 + 週次意思決定レポート
```

2026年最新のAIツール群を使えば、3人の零細企業でも大企業並みの経営基盤を構築できる。重要なのは、**最初の一歩を踏み出すこと**だ。

データ分析、自動化、意思決定支援——AI経営OSは単なる効率化ツールではなく、少人数企業の**生存戦略**そのものだ。

---

**出典:**
- 厚生労働省「職業安定業務統計」（2024年3月） https://www.mhlw.go.jp/stf/newpage_21509.html
- 経済産業省「IT人材需給に関する調査」（2024年） https://www.meti.go.jp/policy/it_policy/jinzai/


## 関連記事

- [【2026年最新】SES単価相場とフリーランス市場の全データ分析 - AI時代のエンジニア年収戦略](https://qiita.com/sescore/items/116c660825f6bc579a44)
- [【2026年最新データ】AIツール時代のエンジニア市場分析｜SESvsフリーランス単価・転向タイミングを徹底解説](https://qiita.com/sescore/items/e6516b35858e635475f0)
- [【2026年最新】SESエンジニアが市場価値を劇的に上げる技術スキル7選とロードマップ](https://qiita.com/sescore/items/80a9af046eef5aae59d0)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/5ab66c40b1844f06cda4

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://freelance.radineer.asia/freelance/register)**

