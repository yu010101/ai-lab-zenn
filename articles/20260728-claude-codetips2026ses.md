---
title: "Claude Code毎日使い倒して気づいた実践Tips集【2026年版】SESエンジニアのフリーランス転身にも効く"
emoji: "🤖"
type: "tech"
topics: ["claude", "ses", "freelance", "data", "ai"]
published: true
---

# Claude Code毎日使い倒して気づいた実践Tips集【2026年版】

SESで3年働いた後、フリーランスに転身して1年が経った。今では仕事の7割をClaude Codeが一緒にやっている。最初は「AIアシスタントでしょ」くらいにしか思っていなかったが、使い方を覚えるにつれて明らかに別物だとわかった。

この記事では、毎日Claude Codeを使い続けて気づいた**本当に効くTips**を書く。公式ドキュメントに書いてあることは省く。実際に動かして確かめたことだけ書く。

---

## CLAUDE.mdが全ての起点になる

最初にやるべきことはこれだ。プロジェクトルートに`CLAUDE.md`を置くと、Claude Codeがそれを必ず読んでからタスクに入る。

```markdown
# プロジェクト概要
Next.js 15 + Supabase + Tailwind v4のWebアプリ。
本番はVercel。ローカルはポート3000。

## 鉄則
- コミットはfeat/fix/chorセマンティクス厳守
- テストなしのPRは出さない（vitest）
- 型エラーは絶対に残さない

## よく使うコマンド
- dev: `npm run dev`
- test: `npm run test`
- build check: `npm run build`

## 触らないファイル
- `.env.local`（手動管理）
- `supabase/migrations/`（CLIで管理）
```

これを書いておくだけで、毎回「このプロジェクトのテストどう動かすんでしたっけ」みたいな質問をしなくなる。Claudeが勝手に文脈を持ってくれる。

グローバルの`~/.claude/CLAUDE.md`にも書ける。自分の場合はここに「コメントは原則書くな」「エラーハンドリングは境界のみ」みたいな自分のコーディングスタイルを置いている。

---

## /planモードは「やってから後悔する」を防ぐ

Claude Codeには`/plan`モードがある。これを使うと、Claudeが実際にコードを書く前に**実装計画だけ**を返してくれる。

実際にやってみた流れ：

```
ユーザー: /plan
ユーザー: Supabaseのauth.usersテーブルにcustom_claimsカラムを追加して、
         RLSポリシーも更新したい
```

Claude Codeが返すのはこういう計画：

```
## 実装計画

1. マイグレーションファイルの作成
   - supabase/migrations/YYYYMMDD_add_custom_claims.sql
   - auth.usersへのカラム追加（jsonb, nullable）

2. 既存RLSポリシーの確認
   - profiles テーブルのポリシーが影響を受ける可能性
   - 要確認: auth.jwt()を使っているポリシーがあるか

3. TypeScript型の更新
   - types/supabase.ts の再生成が必要
   - `supabase gen types typescript` を実行

4. テストの追加
   ...

承認しますか？
```

これで「あ、RLSポリシー全部確認しないといけないんだ」と気づいてから実装できる。無計画に実装してマイグレーション失敗、というのを何度か経験してから毎回使うようになった。

---

## サブエージェントで並列処理する

Claude Codeはタスクによって内部的にサブエージェントを使う。これを意図的に活用できる。

```
以下を並行してやってほしい：
1. src/components/以下の全コンポーネントの型エラーをリストアップ
2. api/以下のエンドポイントに対するテストカバレッジを調べる
3. package.jsonの依存関係で古くなっているものを確認
```

こう書くと、複数のエージェントが同時に動いて結果をまとめてくれる。1つずつ聞くより明らかに速い。

自分が実際に使うのは**コードレビューのとき**。

```
このPRを以下の観点で並行レビューしてほしい：
- セキュリティ（XSS, SQLインジェクション, 認証バイパス）
- パフォーマンス（N+1クエリ, 不要なレンダリング）
- 型安全性（anyの使用, 型アサーション）
- テスト漏れ
```

4つを同時に調べてまとめてくれる。フリーランスで一人で開発しているとレビュアーがいないので、これが実質的なコードレビューになっている。

---

## データ分析タスクでの使い方

データ分析の案件をいくつかやってきたが、Claude Codeが一番活きるのはここだと思っている。

### CSVを読ませて探索的分析をやらせる

```
sales_data.csvを分析してほしい。
まず構造を確認して、欠損値・外れ値・基本統計量を出してから、
売上に影響している変数を探ってほしい。
Pythonで実行可能なコードで出してくれ。
```

Claude Codeはファイルを読んで、実際にPythonコードを書いて、必要なら実行して、結果を解釈するところまでやってくれる。自分で最初からPandas書くのと比べて明らかに速い。

### SQLクエリの最適化

```sql
-- このクエリが遅い。EXPLAINの結果も貼る
SELECT u.name, COUNT(o.id) as order_count, SUM(o.total) as revenue
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE o.created_at >= '2026-01-01'
GROUP BY u.id
ORDER BY revenue DESC;
```

EXPLAINの出力と一緒に貼ると、「このSeq Scanがボトルネック、このインデックスを追加せよ」と具体的に返してくれる。自分でEXPLAIN ANALYZEを読み解くより圧倒的に速い。

### データパイプラインの設計

データ分析案件ではよくETLパイプラインを求められる。Claude Codeに渡す情報：

1. データソース（DB、API、ファイル）
2. 変換要件（正規化、集計、フィルタリング）
3. 出力先（Redshift、BigQuery、Postgres）
4. 実行頻度

これを伝えると、適切なツール選定（dbt vs Airflow vs シンプルなPythonスクリプト）の提案から実装まで一気にやってくれる。

---

## MCPサーバーで外部ツールと繋ぐ

MCP（Model Context Protocol）を使うと、Claude Codeが外部ツールと直接連携できる。

`~/.claude/claude_desktop_config.json`（またはClaude Codeの設定）に以下を追加：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxxxxxx"
      }
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"]
    }
  }
}
```

GitHub MCPを使うと：

```
open PRsを全部確認して、レビューが2日以上止まっているものをリストアップしてくれ
```

これで実際にGitHubのAPIを叩いてPR一覧を取ってきて、作成日時から計算して返してくれる。毎朝やるルーティンをClaude Codeに任せるようになった。

Postgres MCPを使うと：

```
productionのDBのスキーマを確認しながら、
月次の売上レポートを出すクエリを書いてくれ
```

実際のスキーマを参照しながらクエリを書いてくれるので、カラム名の間違いがなくなった。

---

## ホック（Hooks）で自動化する

Claude Codeにはhookの仕組みがある。`~/.claude/settings.json`に設定を書くと、特定のイベントで自動的にコマンドを実行できる。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "npm run typecheck 2>&1 | tail -5"
          }
        ]
      }
    ]
  }
}
```

これを設定すると、Claudeがファイルを編集するたびに型チェックが自動で走る。型エラーが出たらClaude Codeが即座に気づいて修正しようとする。

自分が使っているもう一つの設定：

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "osascript -e 'display notification \"Claude Code finished\" with title \"Done\"'"
          }
        ]
      }
    ]
  }
}
```

Claudeが作業を終えたらMacの通知が来る。長い処理を投げて別のことをしているときに便利。

---

## 長期プロジェクトでのコンテキスト管理

Claude Codeは会話が長くなるとコンテキストが圧縮される。これを意識した使い方が必要。

### セッション開始時のリセット

```
/clear
```

新しいタスクに入るときは必ずこれ。前の会話のゴミが残ると判断がぶれる。

### 重要な決定はCLAUDE.mdに残す

アーキテクチャの決定や「なぜこの実装にしたか」は`CLAUDE.md`に書く。

```markdown
## アーキテクチャ決定記録

### 2026-07-15: キャッシュ戦略
- Redisを使わずにReact Queryのキャッシュのみにしたのはインフラコスト削減のため
- 将来的にはvercel KVを検討

### 2026-07-20: 認証
- Supabase Authを使用。JWTはcookieに保存（httpOnly）
- NextAuth.jsは選ばなかった（Supabaseとの統合が複雑になるため）
```

こうしておくとセッションを新しく始めても、Claudeが過去の決定を把握してくれる。

---

## フリーランス転身後に気づいたこと

SESから離れてフリーランスになったとき、最初にしんどかったのは**事務作業**だった。契約書、見積書、請求書、確定申告の準備——コードを書く以外のことが山積みになる。

ここでもClaude Codeを使っている。

### フリーランス契約書テンプレートの作成

```
以下の条件でフリーランス 契約書 テンプレートを作ってほしい。
日本法準拠、業務委託（請負型）、
知的財産権は成果物の納品後にクライアントへ移転、
報酬は月末締め翌月末払い、
途中解約の場合は既納品分の費用は支払い済みとする。

実際に使えるレベルで書いてくれ。
```

返ってきたテンプレートをベースに、弁護士にレビューしてもらって使っている。ゼロから書くよりはるかに速い。ただし**法的文書は必ず専門家に確認すること**。Claudeは叩き台を作るのが仕事で、法的判断はしない。

### 見積書のロジックを組む

```python
# Claude Codeに書いてもらった見積もり計算スクリプト
def calculate_estimate(
    base_hours: float,
    hourly_rate: int,
    complexity_factor: float = 1.0,
    buffer_ratio: float = 0.2
) -> dict:
    """
    工数見積もり計算
    buffer_ratio: リスクバッファ（デフォルト20%）
    """
    base_cost = base_hours * hourly_rate
    buffered_hours = base_hours * (1 + buffer_ratio)
    total_cost = buffered_hours * hourly_rate * complexity_factor
    
    return {
        "base_hours": base_hours,
        "buffered_hours": buffered_hours,
        "hourly_rate": hourly_rate,
        "total_cost": int(total_cost),
        "tax_10": int(total_cost * 1.1)
    }

# 使用例
result = calculate_estimate(
    base_hours=40,
    hourly_rate=10000,
    complexity_factor=1.2,  # 初めての技術スタックなので20%増
    buffer_ratio=0.25
)
print(f"合計（税抜）: ¥{result['total_cost']:,}")
print(f"合計（税込）: ¥{result['tax_10']:,}")
```

---

## 実際に失敗したこと

正直に書く。

**失敗1: Claudeを信用しすぎてレビューしなかった**

Claude Codeが生成したSQLマイグレーションをそのまま本番に流した。テーブルのロック時間の見積もりが甘くて、5分くらいサービスが重くなった。Claudeが「このマイグレーションは大丈夫」と言っても、本番適用前に自分でEXPLAIN ANALYZEするのは人間の仕事。

**失敗2: コンテキストが汚染された状態で続けた**

会話が長くなった状態でバグ修正を頼んだら、前の話題のコードを参照して全然関係ない修正をしてきた。長い会話は`/clear`でリセットするのが正解。

**失敗3: 曖昧な指示で時間を無駄にした**

「このAPIをよくして」という指示を出したら、パフォーマンス改善をやってきた。自分はエラーハンドリングを直してほしかった。Claudeへの指示は**具体的**に書く。「このAPIのエラーハンドリングを改善して。特にネットワークエラーとタイムアウトの処理が漏れている」のように。

---

## SESがつらいと感じたときの選択肢としてのAI活用

SESつらいという声をよく聞く。客先常駐で自分の技術が伸びている感覚がない、単価が上がらない、案件を選べない——これは構造的な問題だ。

AIツールを使いこなすことが、そこからの出口になりうる。具体的には：

1. **副業案件の質が上がる**: Claude Codeを使うとSES稼働中でも週末の副業でそれなりのものが作れる。ポートフォリオが充実する。

2. **技術的な差別化ができる**: AI活用スキルは今後数年で標準になる前に習得しておいた方がいい。先行者利益はまだある。

3. **フリーランスへの移行準備**: データ分析、バックエンド、フロントエンドのどのスキルセットでも、Claude Codeで生産性を上げておくと独立後の単価交渉で有利になる。

自分もSES期間中にClaude Code（当時はまだ初期バージョン）で副業案件を回して実績を作り、それを元にフリーランス転身の説得材料にした。

---

## まとめ：明日から使えるTips一覧

| Tip | 効果 | 難易度 |
|---|---|---|
| `CLAUDE.md`を書く | 毎回の説明が不要になる | ★☆☆ |
| `/plan`モードを使う | 実装前に問題に気づける | ★☆☆ |
| 並行タスクを明示する | 処理速度が上がる | ★☆☆ |
| MCPサーバーを繋ぐ | 外部ツールとシームレスに | ★★☆ |
| Hooksを設定する | 型チェック等が自動化 | ★★☆ |
| セッションをこまめにリセット | コンテキスト汚染を防ぐ | ★☆☆ |
| EXPLAINの結果を一緒に貼る | SQLチューニングの精度UP | ★☆☆ |

Claude Codeは使い込むほどに返ってくる投資対効果が上がるツールだ。最初の1週間は設定に時間をかけて、その後は実際のプロジェクトで毎日触るのが一番の近道だった。


## 関連記事

- [SESエンジニアがフリーランス独立前に絶対確認すべき税務・節税の全知識【2026年最新版】](https://qiita.com/sescore/items/508398300d7d26e26a40)
- [OpenClaw×Claude Code連携実践録——SES脱出を加速するAI開発OSの全貌2026](https://qiita.com/sescore/items/919fc2c210407303f471)
- [【2026年最新】開発生産性ツール完全比較：Warp・Raycast・Linear・Notionなど6選をエンジニアがTier分けしてみた](https://qiita.com/sescore/items/a2aeb5058ad5f90c89f7)

---

**AI駆動塾 — AIを使ったスモビジの作り方を学ぶ**

Claude Code、OpenClaw、AI経営OSの実践ノウハウを毎週公開中。
月額¥4,980で過去記事すべて読み放題。

[noteメンバーシップに参加する →](https://note.com/l_mrk/membership)

---

Qiitaでコード付き解説も公開しています: https://qiita.com/sescore/items/88f8ce268734e761bcac

---

## 💼 フリーランスエンジニアの案件をお探しですか？

**SES解体新書 フリーランスDB**では、高単価案件を多数掲載中です。

- ✅ マージン率公開で透明な取引
- ✅ AI/クラウド/Web系の厳選案件
- ✅ 専任コーディネーターが単価交渉をサポート

▶ **[無料でエンジニア登録する](https://radineer.asia/freelance/register?utm_source=zenn&utm_medium=article&utm_campaign=claude-code%E6%AF%8E%E6%97%A5%E4%BD%BF%E3%81%84%E5%80%92%E3%81%97%E3%81%A6%E6%B0%97%E3%81%A5%E3%81%84%E3%81%9F%E5%AE%9F%E8%B7%B5tips%E9%9B%86-2026%E5%B9%B4%E7%89%88-ses%E3%82%A8%E3%83%B3%E3%82%B8%E3%83%8B%E3%82%A2%E3%81%AE%E3%83%95%E3%83%AA%E3%83%BC%E3%83%A9%E3%83%B3%E3%82%B9%E8%BB%A2%E8%BA%AB%E3%81%AB%E3%82%82%E5%8A%B9%E3%81%8F)**

