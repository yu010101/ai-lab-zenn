---
title: "3人会社がAI経営OSを作った話｜CFO・CMO・COOをAIにした2026年のリアル"
emoji: "🤖"
type: "tech"
topics: ["ai", "data", "freelance", "ses", "claude"]
published: true
---

# 3人会社がAI経営OSを作った話｜CFO・CMO・COOをAIにした2026年のリアル

「SESつらい」と思い始めたのは、客先で毎日Excel集計をしていた頃だった。

データ分析の仕事は面白い。でも**意思決定は全部クライアント側にある**。自分がどれだけ精緻な分析を出しても、最終的に判断するのは別の人間。そのもどかしさが積み重なって、2023年にSESからフリーランスへ転向した。

そして今、2026年現在、私は3人の会社を経営している。月商250万円。クライアントは5社。そして**CFO・CMO・COOの役割は全部AIエージェントが担っている**。

これは「AIすごい」という話ではなく、**3人しかいない会社がどうやってAI経営OSを実際に動かしているか**の、泥臭いリアルな記録だ。

---

## SESからフリーランス、そして3人の会社へ

SESエンジニアの最大の不満は「技術は磨けるが、意思決定から切り離されている」という構造的な問題にある。データ分析スキルを積んで単価を上げても、事業の上流に入れるわけじゃない。

**SESつらい**と感じるエンジニアの多くは、技術力の問題ではなく「自分の判断で動けない」ストレスを抱えている。

フリーランスになって最初の2年は良かった。自分でクライアントを選び、提案し、実装し、納品する。全部自分のジャッジ。でも売上が月200万を超えたあたりで、別の問題が顕在化した。

**意思決定の量が多すぎる。**

- 来月のキャッシュフローは大丈夫か？
- このクライアントの案件は受けるべきか？
- マーケティングに時間を使うべきか、開発に集中すべきか？
- 採用するなら何をアウトソースすべきか？

これ全部、一人でやりながら開発もする。人を雇っても2〜3人では経営管理職なんて置けない。**そこでAI経営OSを作ることにした。**

---

## AI経営OSとは何か：作ったものの全体像

私が構築したのは、**Claude Code + MCP + カスタムスキルで動くAIエージェント群**だ。名前は「OpenClaw」と呼んでいる。

役割は以下の通り：

| エージェント | 担当業務 | 実行頻度 |
|---|---|---|
| /cfo | 月次PL確認・キャッシュフロー予測・請求管理 | 月3回 |
| /cmo | SNS投稿・コンテンツ戦略・SEO分析 | 毎日 |
| /coo | タスク優先度・プロジェクト進捗管理 | 毎朝 |
| /ceo | 週次戦略レビュー・意思決定ログ | 週1回 |
| /research-scout | 市場調査・競合分析 | 随時 |

これは単なる「ChatGPTに聞く」ではない。**各エージェントは会社の実データ（売上、タスク、クライアント情報）にアクセスし、文脈を持って動く。**

---

## 実装の核心：どう作ったか

### Step 1: Claude Codeのスキルシステムを使う

Claude Codeには「スキル」という仕組みがある。Markdownで役割・ツール・制約を定義すると、`/skill-name`で呼び出せる専門エージェントになる。

```markdown
# /cfo スキル定義（抜粋）

## Role
You are the CFO of a 3-person company with ¥2.5M monthly revenue.
Analyze actual financial data and provide cash flow forecasts.

## Tools Available
- Read: Access to financial CSV exports
- Bash: Query database for invoice status
- WebFetch: Check market benchmarks

## Constraints
- 架空の数字を使わない
- データがない場合は「データ不足」と明示
- ピーク値を再現可能値として扱わない
```

### Step 2: 実データとの接続（MCPサーバー）

エージェントが本当に役立つのは、**リアルデータにアクセスできるとき**だ。

```typescript
// mcp-server/financial.ts
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { neon } from '@neondatabase/serverless';

const sql = neon(process.env.DATABASE_URL!);

server.tool('get_monthly_revenue', async ({ month }: { month: string }) => {
  const rows = await sql`
    SELECT SUM(amount) as revenue, COUNT(*) as invoice_count
    FROM invoices 
    WHERE DATE_TRUNC('month', issued_at) = ${month}::date
    AND status = 'paid'
  `;
  return { revenue: rows[0].revenue, invoices: rows[0].invoice_count };
});
```

これでCFOエージェントは「今月の売上はいくらか」を実際のDBに問い合わせて答える。Excelで集計する必要がなくなった。

### Step 3: cronで自動実行

```bash
# PM2 ecosystem.config.js（抜粋）
{
  name: 'coo-morning-brief',
  script: 'claude -p "/coo 今日のタスク優先度を確認して昨日の未完了分と合わせてブリーフィングして" \
           --output-format json > /tmp/coo-brief.json',
  cron_restart: '30 8 * * 1-5',  // 平日8:30
  autorestart: false
}
```

注意点：macOSではlaunchdではなくPM2を使う。launchdは無音で停止することがあり、気づかないまま何週間も自動化が止まっていた経験がある。

---

## つまずいたポイント：正直な失敗談

### 失敗1: 「賢いエージェント」幻想

最初は「プロンプトを詳しく書けば何でもやってくれる」と思っていた。現実は違う。

**データがなければ、どんなに賢いエージェントも嘘をつく。**

CFOエージェントに「来月の資金繰りは？」と聞いたら、もっともらしい数字を出してきた。でも根拠は？実際のデータとの接続がないと、エージェントは「それらしい回答」を生成するだけだ。

→ **解決策：実データとの接続が先、エージェント構築は後。** MCPサーバーで実際のDB・スプレッドシート・タスク管理ツールと繋いでから、初めてエージェントが機能する。

### 失敗2: SNS自動投稿の暴走

CMOエージェントに「毎日コンテンツを投稿して」と設定したら、同じアカウントに15分以内に連続投稿してしまった。

**Metaのシャドウバンを食らった。**（2026年4月の実体験）

→ **解決策：自動投稿は下書きまで。公開は人間が承認するフローにした。** コードで言えば：

```python
# sns_poster.py
def create_draft(content: str, platform: str) -> dict:
    """下書きを作成し、人間承認キューに追加"""
    draft = {
        'content': content,
        'platform': platform,
        'status': 'pending_approval',  # 自動でpublishedにしない
        'created_at': datetime.now().isoformat()
    }
    # Slackに通知して人間に確認を求める
    notify_slack(f"投稿候補が届いています。承認してください:\n{content[:100]}...")
    return draft
```

### 失敗3: コンテキスト汚染

長い会話の中でエージェントに複数の役割をさせると、前の指示が後の判断に影響する。「CFOとして分析して、次にCMOとして施策を考えて」は動作が不安定になる。

→ **解決策：1エージェント1タスク。** 役割をまたぐ場合は新しいセッションを開始する。

---

## 実際に変わったこと：6ヶ月動かしての所感

### 変わった①: 意思決定の質が上がった

以前は「なんとなく来月厳しそう」という感覚で仕事を受けていた。今はCFOエージェントが毎月初に以下を出力する：

```
【6月キャッシュフロー予測】
- 確定売上: ¥1,820,000（請求済み3件）
- 見込み売上: ¥650,000（進行中2件、完了予定6/20）
- 固定費合計: ¥480,000
- 予想月末残高: ¥1,990,000

【アラート】
B社案件の検収が遅延しています。7月にキャリーオーバーすると
7月前半のキャッシュが薄くなります。先方に確認を推奨。
```

これは**実際のDBデータから計算した数字**だ。感覚ではなくデータで動けるようになった。

### 変わった②: コンテンツ生産量が増えた

ブログ・SNS・メルマガ。以前は書く時間がなかった。今はCMOエージェントが「今日のトレンド×自社の専門性」で記事の草案を毎日生成する。

私がやることは：
1. 草案をレビュー（15分）
2. 自分の体験談を追記（10分）
3. 承認ボタンを押す（1分）

コンテンツ数は以前の約3倍になった。

### 変わった③: 変わらなかったこと

正直に言う。**売上は劇的には変わっていない。**

AIが経営を変えるとよく言われるが、3人の小さな会社では「営業力」「信頼関係」「技術力」が売上の大半を決める。AIは**意思決定の質と実行速度**を上げるツールであり、魔法の杖ではない。

ただ、**意思決定のストレスは明らかに減った。** これが3人経営の最大の価値かもしれない。

---

## データ分析エンジニアがAI経営OSを作るべき理由

SESからフリーランスになった、あるいは独立を考えているデータ分析エンジニアへ。

**あなたには他の職種より有利な点がある。**

1. **データパイプラインの設計ができる** → MCPサーバーの実装は「ETLパイプライン」と同じ思考で作れる
2. **ダッシュボード設計の経験がある** → エージェントのアウトプット設計に直結する
3. **「分析→判断」の思考が身についている** → エージェントに何を聞くべきかを知っている

SESでの「データ分析」経験は、AI経営OSを構築する上で直接使えるスキルだ。

---

## 実装したい人へ：最小構成のスタートライン

「全部作る」と思うと始められない。最小構成から始めよ。

```bash
# Step 1: Claude Codeをインストール
npm install -g @anthropic-ai/claude-code

# Step 2: プロジェクトの.claude/skills/に最初のエージェントを作る
mkdir -p .claude/skills
cat > .claude/skills/cfo.md << 'EOF'
---
title: CFO Agent
description: Monthly financial review agent
---

You are the CFO. When called, ask for this month's revenue and expenses,
then output a simple cash flow summary and one actionable insight.
Always ask for actual data. Never fabricate numbers.
EOF

# Step 3: 呼び出す
claude '/cfo 今月の収支をレビューして'
```

まずこれだけでいい。実データとの接続は、使いながら少しずつ繋いでいく。

---

## 2026年のSESエンジニアへ：フリーランスへの道

**SES つらい**と感じているなら、それは正直なシグナルだ。

2026年現在、データ分析スキルを持つエンジニアの市場価値は高い。AIツールの普及で「AIに指示を出せる人間」の需要が増しており、データ構造を理解してAIエージェントを設計できるエンジニアは希少だ。

SESからフリーランスへの移行で最初に壁になるのは「営業」だが、これもAIでサポートできる。提案書の草案、見積もりの計算、クライアントへのフォローアップメールの下書き。これらは全部エージェントに任せられる。

**「意思決定を自分でしたい」というエンジニアには、今がチャンスだ。**

---

## まとめ：AI経営OSを作って学んだこと

| 項目 | 作る前の想定 | 実際 |
|---|---|---|
| 構築時間 | 1週間 | 3ヶ月（データ接続込み） |
| 一番難しいこと | プロンプト設計 | 実データとの接続 |
| 一番効果があったこと | 売上増加 | 意思決定ストレスの軽減 |
| 一番の失敗 | SNS自動投稿の暴走 | シャドウバン（実体験） |

AI経営OSは「夢のツール」ではなく、**地道に実データと繋いでいく工事**だ。でも一度動き始めると、3人でも「経営管理機能を持った会社」として動けるようになる。

SES→フリーランス→小さな会社。この道を歩いてきて、**一番効いたのはスキルより「自分で意思決定する習慣」だった。** AIはその習慣をサポートするツールに過ぎない。でも、そのサポートがあるとないとでは、精神的な負荷がまるで違う。

興味があれば、まず`/cfo`エージェントを一つ作るところから始めてみてほしい。


## 関連記事

- [OpenClawで「AI経営OS」を構築してみた：9体のエージェントの設定方法と経営効果【2026年】](https://qiita.com/sescore/items/c23dd0264cb1b26158f1)
- [Claude Code実践Tips集2026年最新版：毎日使う開発者が教える本当に使えるテクニック](https://qiita.com/sescore/items/8a25772fdb0f2e12681c)
- [SESやめたいエンジニアが2026年にAIで年収800万を超える方法【徹底解説】](https://qiita.com/sescore/items/d67da3910ca99effb1fb)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/a6d40ea3e2ec927fd8f1

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://radineer.asia/freelance/register?utm_source=zenn&utm_medium=article&utm_campaign=3%E4%BA%BA%E4%BC%9A%E7%A4%BE%E3%81%8Cai%E7%B5%8C%E5%96%B6os%E3%82%92%E4%BD%9C%E3%81%A3%E3%81%9F%E8%A9%B1-cfo%E3%83%BBcmo%E3%83%BBcoo%E3%82%92ai%E3%81%AB%E3%81%97%E3%81%9F2026%E5%B9%B4%E3%81%AE%E3%83%AA%E3%82%A2%E3%83%AB)**

