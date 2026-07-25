---
title: "3人会社でAI経営OSを構築した全記録——CFO・CMO・CEOエージェントが月商250万の会社を変えた話"
emoji: "🤖"
type: "tech"
topics: ["freelance", "ses", "ai", "claude", "agent"]
published: true
---

## TL;DR

- 従業員3名・月商250万円のスモールビジネスでAI経営OSを構築
- CFO（資金/PL管理）・CMO（コンテンツ戦略）・COO（タスク/オペレーション）・CEO（意思決定統合）の4役をAIエージェントで実装
- Claude Code + Anthropic SDK + 自作CLIで構成、mac miniをPM2で常時稼働
- つまずきポイントと実際の変化をエンジニア視点で赤裸々に公開

---

## はじめに：「経営の認知コスト」という見えない壁

元SESエンジニアとして言わせてほしいのだが、SES・フリーランス問わず **年収800万の壁** は技術力より「経営判断の遅さ」で決まることが多い。

単価相場が上がっても、自分のキャパシティ管理・営業戦略・財務判断が追いつかなければ収入は頭打ちになる。フリーランスとして独立後に痛感したのはこの点だった。

毎月のPL確認、コンテンツ計画、タスク整理、進捗レポート——これらを全部自分でやると、純粋な開発稼働が週20時間を割り込むことがある。SES 単価 相場がどれだけ上がっても、稼働時間が半減すれば年収は上がらない。

2026年に入ってから、3人チームで**AI経営OS**——つまりAIエージェントたちが自分の代わりに経営の各機能を担う仕組み——を本格的に構築した。この記事では、その設計・実装・つまずき・効果をエンジニア視点でできるだけ具体的に書く。

---

## AI経営OSとは何か

シンプルに言うと、**人間のCFO・CMO・COO・CEOがやる仕事をAIエージェントに分担させるシステム**だ。

| エージェント | 担当領域 | 主な出力 |
|---|---|---|
| CFO | PL分析・キャッシュフロー予測・コスト最適化 | 月次財務レポート・アクション提案 |
| CMO | コンテンツ戦略・SNS投稿計画・KPI分析 | 投稿下書き候補・多様性スコア |
| COO | タスク管理・オペレーション監視・日次報告 | ヘルスチェック結果・異常検知 |
| CEO | 4エージェントの報告統合・週次意思決定サマリ | 今週の最重要アクション3項目 |

「AI経営OS」という言葉を聞くと大企業向けに聞こえるかもしれないが、逆だ。**3人チームだからこそ機能する**。意思決定者が少ないので、AIの提案をそのまま採用できる速度が速い。大企業では「AIの提案を誰が承認するか」という政治が発生するが、3人なら翌朝のミーティング前に実装まで終わる。

---

## アーキテクチャ設計

### 全体構成

```
[ macOS cron (PM2管理) ]
    ↓ 毎朝7:00
[ orchestrator.ts ]
    ├── /cfo  → CFOエージェント（PL分析）
    ├── /cmo  → CMOエージェント（コンテンツ戦略）
    ├── /coo  → COOエージェント（オペレーション監視）
    └── /ceo  → 統合レポート生成
    
[ Claude Code (対話型) ]
    ↓ 呼び出し
[ 各スキルファイル (.claude/skills/) ]
```

インフラはmac mini（常設）＋PM2でのプロセス管理。cronはlaunchdではなくPM2を使う。macOSのlaunchdは無音停止するリスクがあり、止まっていることに気づかない事態が過去に発生した。PM2なら`pm2 list`で即座に確認できる。

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'keiei-os-daily',
    script: 'scripts/daily-orchestrator.ts',
    interpreter: 'tsx',
    cron_restart: '0 7 * * *',
    watch: false,
    env: { NODE_ENV: 'production' }
  }]
}
```

データベースはNeon DB（PostgreSQL SaaS）を使用。接続文字列は`neonctl connection-string`で毎回動的取得する。`psql ""`（引数なし）はローカルDBに化けるので、必ず接続文字列を明示的に渡す。

---

## 実装編①：CFOエージェント

CFOが最初に着手すべき理由は単純で、「お金の状況が把握できないとCMOもCOOも戦略を立てられない」からだ。財務の現実を無視したコンテンツ計画やオペレーション改善は空振りに終わる。

### DB設計

```sql
-- 月次売上・コストテーブル
CREATE TABLE monthly_pl (
  id SERIAL PRIMARY KEY,
  month DATE NOT NULL,
  revenue INTEGER NOT NULL,
  cost_labor INTEGER DEFAULT 0,
  cost_tool INTEGER DEFAULT 0,
  cost_ads INTEGER DEFAULT 0,
  cost_other INTEGER DEFAULT 0,
  gross_profit INTEGER GENERATED ALWAYS AS (
    revenue - cost_labor - cost_tool - cost_ads - cost_other
  ) STORED,
  memo TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_monthly_pl_month ON monthly_pl(month DESC);
```

### CFOエージェントのプロンプト設計

```typescript
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic();

interface PLData {
  month: string;
  revenue: number;
  cost_labor: number;
  cost_tool: number;
  cost_ads: number;
  gross_profit: number;
}

async function runCFO(monthlyData: PLData[]) {
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 4096,
    system: `あなたはスタートアップのCFOです。
月次PLデータを分析し、以下を必ず含む経営レポートを作成してください：
1. 前月比の変化と要因分析
2. 3ヶ月のキャッシュフロー予測（根拠を明示）
3. コスト削減の具体的な提案（実行可能なものだけ）
4. 次月の優先アクション（3項目以内）

【重要】
- 数値は提供されたデータのみ使用。推測は「推測:」と冒頭に明示すること
- 存在しないデータからの計算は行わないこと`,
    messages: [{
      role: 'user',
      content: `直近3ヶ月のPLデータ:\n${JSON.stringify(monthlyData, null, 2)}`
    }]
  });
  
  return response.content[0].type === 'text' 
    ? response.content[0].text 
    : '';
}
```

### バリデーション層の必要性

最初のバージョンで大きく失敗した。Claude が**存在しない数値を自信満々に「分析」して報告**してきた。「前月比23%増」という数値がレポートに載っていたが、実際のデータを確認すると7%増だった。

対策として採用したのが数値突合バリデーション：

```typescript
function validateCFOReport(report: string, sourceData: PLData[]) {
  const latest = sourceData[sourceData.length - 1];
  
  // レポート内の売上数値を抽出
  const revenueMatches = report.matchAll(/売上[：:]\s*[¥￥]?([\d,]+)/g);
  for (const match of revenueMatches) {
    const reported = parseInt(match[1].replace(/,/g, ''));
    if (Math.abs(reported - latest.revenue) > 50000) {
      console.warn(`[CFO警告] 数値乖離: 報告=${reported}, 実際=${latest.revenue}`);
      // Slack通知 or ログ記録
    }
  }
}
```

---

## 実装編②：CMOエージェント

CMOの主な仕事は「コンテンツカレンダーの設計」と「投稿ネタの生成」だ。

### SNS自動化の鉄則：下書きまで、公開は人間が判断

**SNS投稿の自動公開は絶対にやってはいけない。**

同一アカウントへの連投を短時間で行うとプラットフォーム側のペナルティを受けるリスクがある。CMOエージェントが生成するのは**下書き候補まで**に限定している。公開は必ず人間が確認してから行う。

```typescript
const CMO_SYSTEM_PROMPT = `
あなたはSNS/コンテンツ戦略のCMOです。

【絶対制約】
- 生成するのは「下書き候補」のみ。自動公開処理は実行しない
- 同一アカウントへの投稿は最低15分間隔を提案に含めること
- 架空の数値・実績・体験談は一切書かない
- 現在運用中でないサービスを「稼働中」と表現しない

出力形式（JSON）:
{
  "post_candidates": [
    {
      "platform": "X",
      "body": "投稿本文",
      "earliest_post_time": "YYYY-MM-DD HH:mm",
      "requires_human_approval": true,
      "topic_category": "技術/事例/告知"
    }
  ],
  "diversity_warning": "偏りがある場合のみ記載"
}
`;
```

### コンテンツ多様性スコアの実装

同じトピックが続くとエンゲージメントが落ちる。これを防ぐために「多様性スコア」をShannon エントロピーで計算している。

```typescript
interface ContentDiversityAnalysis {
  topicFrequency: Record<string, number>;
  diversityScore: number; // 0.0（偏り大） ~ 1.0（均等）
  underservedTopics: string[];
  recommendation: string;
}

function analyzeDiversity(recentPosts: Post[]): ContentDiversityAnalysis {
  const topics = recentPosts.map(p => p.topic_category);
  const frequency: Record<string, number> = {};
  
  topics.forEach(t => {
    frequency[t] = (frequency[t] || 0) + 1;
  });
  
  // Shannon entropy
  const total = topics.length;
  const entropy = Object.values(frequency).reduce((acc, count) => {
    const p = count / total;
    return acc - p * Math.log2(p);
  }, 0);
  
  const maxEntropy = Math.log2(Object.keys(frequency).length || 1);
  const diversityScore = maxEntropy > 0 ? entropy / maxEntropy : 0;
  
  const allTopics = ['技術解説', '事例紹介', '市場分析', 'ツール比較', 'ノウハウ'];
  const underserved = allTopics.filter(
    t => !frequency[t] || (frequency[t] / total) < 0.1
  );
  
  return {
    topicFrequency: frequency,
    diversityScore,
    underservedTopics: underserved,
    recommendation: diversityScore < 0.5 
      ? `多様性スコア低下中(${diversityScore.toFixed(2)})。${underserved.join('/')}を増やすこと` 
      : 'バランス良好'
  };
}
```

---

## 実装編③：COO＋CEO統合

COOは「日々のオペレーション監視」が主な役割だ。デプロイ状況・DB接続・cron実行ログ・エラー率を毎朝チェックして報告してくれる。

```bash
#!/bin/bash
# coo-daily-check.sh

echo "=== COO Daily Check $(date '+%Y-%m-%d %H:%M') ==="

# PM2プロセス確認
echo "[プロセス状況]"
pm2 list | grep -E 'name|online|errored|stopped'

# Claude認証確認（失敗すると全cronが401で止まる最優先監視対象）
if claude --version > /dev/null 2>&1; then
  echo "[Claude認証] OK"
else
  echo "[Claude認証] 要再認証 - 全cron停止リスク"
  # 通知処理
fi

# DB接続確認（neonctlで毎回取得）
CONNECTION=$(neonctl connection-string --project-id "$NEON_PROJECT_ID")
if psql "$CONNECTION" -c "SELECT 1" > /dev/null 2>&1; then
  echo "[DB] 接続OK"
else
  echo "[DB] 接続失敗 - 要確認"
fi

# 24時間エラーカウント
ERROR_COUNT=$(psql "$CONNECTION" -t -c "
  SELECT COUNT(*) FROM error_logs
  WHERE created_at > NOW() - INTERVAL '24 hours'
" 2>/dev/null | xargs)
echo "[エラー数 24h] ${ERROR_COUNT:-取得失敗}"
```

CEOエージェントはCFO・CMO・COOの出力を受け取り、週次の経営サマリを生成する：

```typescript
async function runCEO(reports: {
  cfo: string;
  cmo: string;
  coo: string;
  sharedContext: SharedContext;
}) {
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 2048,
    system: `あなたは3名チームのCEOです。
CFO・CMO・COOの週次レポートを統合し、
今週の最重要アクション3項目を決定してください。

判断基準：
1. 財務インパクトが最大のもの優先
2. 1週間以内に実行可能なもの優先
3. チーム3名のキャパを考慮（1人週約20時間の開発稼働）
4. 推測・仮定に基づくアクションは「要検証:」と明記すること`,
    messages: [{
      role: 'user',
      content: [
        `## CFOレポート\n${reports.cfo}`,
        `## CMOレポート\n${reports.cmo}`,
        `## COOレポート\n${reports.coo}`,
        `## 共有コンテキスト\n${JSON.stringify(reports.sharedContext, null, 2)}`
      ].join('\n\n')
    }]
  });

  return response.content[0].type === 'text' ? response.content[0].text : '';
}
```

---

## つまずいたポイント——全部晒す

### つまずき①：コスト事故のリスク管理

AnthropicのAPIをループ処理から呼び出すコードにバグがあると、一晩でトークンが大量消費されるリスクがある。有料LLM/APIの直叩きは常にコスト事故と隣り合わせだ。

今は必ず呼び出し回数の日次上限とトークン上限をハードコードしている：

```typescript
const DAILY_CALL_LIMIT = 50;
const DAILY_TOKEN_BUDGET = 100_000;
let callCount = 0;
let totalTokensUsed = 0;

async function safeAgentCall(
  prompt: string,
  opts: { maxTokens?: number } = {}
): Promise<string> {
  if (callCount >= DAILY_CALL_LIMIT) {
    throw new Error(`日次API呼び出し上限(${DAILY_CALL_LIMIT}回)に達しました`);
  }
  if (totalTokensUsed >= DAILY_TOKEN_BUDGET) {
    throw new Error(`日次トークン予算(${DAILY_TOKEN_BUDGET})に達しました`);
  }
  
  callCount++;
  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: opts.maxTokens ?? 2048,
    messages: [{ role: 'user', content: prompt }]
  });
  
  totalTokensUsed += response.usage.input_tokens + response.usage.output_tokens;
  return response.content[0].type === 'text' ? response.content[0].text : '';
}
```

### つまずき②：エージェント間の文脈共有

CFOの出力をCMOが知らずに矛盾した戦略を立てる問題が発生した。「コスト削減フェーズ中」なのにCMOが「広告予算増加を提案」するケースだ。

解決策は「共有コンテキストファイル」の導入：

```typescript
interface SharedContext {
  lastUpdated: string; // ISO8601
  currentPhase: 'growth' | 'cost-reduction' | 'stable';
  currentMonth: {
    revenue: number;
    costBudgetRemaining: number;
    priorityFocus: string;
  };
  flags: {
    hasCashflowWarning: boolean;
    isContentPivotNeeded: boolean;
    hasOpsAlert: boolean;
  };
}

// 各エージェント実行前に読み込み、実行後に更新
async function loadSharedContext(): Promise<SharedContext> {
  const raw = await fs.readFile('.keiei-os/shared-context.json', 'utf-8');
  return JSON.parse(raw);
}

async function updateSharedContext(updates: Partial<SharedContext>) {
  const current = await loadSharedContext();
  const updated = { ...current, ...updates, lastUpdated: new Date().toISOString() };
  await fs.writeFile(
    '.keiei-os/shared-context.json',
    JSON.stringify(updated, null, 2)
  );
}
```

### つまずき③：Hallucination（幻覚）の扱い

エージェントが「先月比20%増」と言っても実際には5%増だった、というケースを複数回経験した。これはモデルの問題というより、**プロンプト設計の問題**だと気づいた。

改善前：「売上の推移を分析してください」（文脈からの推測を許してしまう）

改善後：「以下のJSONデータだけを参照して分析してください。データに存在しない数値は一切使用しないこと」（データを明示的に渡す）

この変更後、数値幻覚はほぼゼロになった。**「何を見て良いか」を明示することがプロンプト設計の要点**だ。

### つまずき④：Claude認証の維持

Claude Code CLIを使うcronジョブは、claude認証トークンが失効すると**全cron一斉に401エラーで止まる**。これが最も致命的な障害だった。

対策：COOエージェントの日次チェックに必ずclaude認証確認を含め、失効が近づいたら即座にアラートを上げるようにしている。

---

## 実際の変化——正直に書く

**言えること（定量）：**

月次のPL確認・コンテンツ計画・タスク整理をまとめて以前は半日程度かけていた。今は毎朝のCEOサマリを読む15〜20分で週次の優先事項が決まり、その分だけ開発稼働に回せるようになった。

**言えること（定性）：**

- 「なぜこの数字か」の説明を毎回考えなくていい（CFOが書いてくれる）
- コンテンツが偏っていないか毎回手動でチェックしなくていい（CMOの多様性スコアが警告する）
- デプロイ後のヘルスチェックを毎朝手動でやらなくていい（COOが報告する）
- 3人の間での「週の方針共有」コストが下がった（CEOサマリを読めば揃う）

**言えないこと（誇張を避ける）：**

「AIが経営を改善した」という大げさな主張はしない。AIは情報整理と案出しを高速化するが、**最終判断は常に人間が行う**。CFOが「コスト削減を提案」しても、それを実行するかどうかは人間が決める。

AIエージェントはあくまで「優秀なアシスタント」であり「経営の自動化」ではない。この区別を間違えると、AIの提案をそのまま実行して後悔することになる。

---

## Claude Codeをこのシステムに組み込む方法

AI経営OSの対話型インターフェースとして、Claude Codeのカスタムスキル機能を使っている。`.claude/skills/`配下にエージェント定義ファイルを置くことで、CLIから直接各エージェントを呼び出せる。

```
.claude/
  skills/
    cfo.md          # CFOエージェントのスキル定義
    cmo.md          # CMOエージェントのスキル定義
    coo.md          # COOエージェントのスキル定義
    ceo.md          # CEO統合スキル
    dash.md         # ダッシュボード表示
    pl.md           # PLデータ入力補助
```

各スキルファイルには役割・制約・ツール定義・出力フォーマットを記述する。Claude Codeがスキルを読み込んで実行することで、ターミナルから`/cfo`と打つだけでCFOエージェントが起動する構成だ。

---

## フリーランス・SESエンジニアへの示唆

SES 単価 相場の話や フリーランス 年収800万 の話をするとき、多くの人は「スキルアップ」に着目する。それは正しい。

ただし独立後に収入が伸び悩む人の多くは、**経営判断の遅さとオペレーション管理の属人化**が原因だ。SES 年収 の上限が技術力ではなく「一人でこなせる経営タスクの量」によって制約されているケースは珍しくない。

AI経営OSはその制約を取り除くための実装だ。3人でも、ひとり社長でも使える。

---

## おわりに：やってみた感想

正直に言うと、**構築に約3ヶ月かかった**。特に「エージェントが幻覚を起こす問題」への対処と「エージェント間の文脈共有設計」が予想以上に難しかった。

これは「完璧なシステムを作る」話ではない。**「人間が見落としやすい部分をAIにカバーさせる」**というアシスタント設計の話だ。

AIが間違えることは前提として受け入れる。そのうえで、どこにバリデーション層を入れるか、どこに人間の判断を残すか——これがAI経営OS設計の本質だと思っている。

コードは随時アップデートしているので、具体的な実装で詰まったことがあればnoteのコメント欄で聞いてほしい。


## 関連記事

- [OpenClaw×Claude Code連携で年収が変わる：SESエンジニアの実践ワークフロー全公開](https://qiita.com/sescore/items/cd0c35a1b8e79a87babf)
- [3人会社にAI経営OSを実装した全記録——CFO/COO/CMOエージェントの作り方と月商250万円の変化](https://qiita.com/sescore/items/0a54bf1232c0b290cbf4)
- [2026年最新｜OpenClawで経営OSを自作した話——9体のAIエージェントが会社を回す](https://qiita.com/sescore/items/1b0f47d7d3885a38995e)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/697565e13dd51e76b935

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://radineer.asia/freelance/register?utm_source=zenn&utm_medium=article&utm_campaign=3%E4%BA%BA%E4%BC%9A%E7%A4%BE%E3%81%A7ai%E7%B5%8C%E5%96%B6os%E3%82%92%E6%A7%8B%E7%AF%89%E3%81%97%E3%81%9F%E5%85%A8%E8%A8%98%E9%8C%B2-cfo%E3%83%BBcmo%E3%83%BBceo%E3%82%A8%E3%83%BC%E3%82%B8%E3%82%A7%E3%83%B3%E3%83%88%E3%81%8C%E6%9C%88%E5%95%86250%E4%B8%87%E3%81%AE%E4%BC%9A%E7%A4%BE%E3%82%92%E5%A4%89%E3%81%88%E3%81%9F%E8%A9%B1)**

