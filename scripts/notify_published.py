#!/usr/bin/env python3
"""Zennで実際に公開された記事だけをChatworkへ通知する。

なぜ必要か: 記事パイプラインは `git push` が成功した時点で success:true と
URL を返すが、Zenn の公開は先入れ先出しで 2.6日に1本しか進まない。
push 直後の URL は 404 で、そのまま通知すると存在しないURLを配ることになる。
だからこのスクリプトは push を見ない。**Zenn API に slug が現れたか**だけを見る。

状態は .zenn-notified.json (通知済み slug の集合)。
通知に失敗した slug は状態に入れない = 次回リトライされる。握り潰さないこと。
"""
import json, os, sys, urllib.parse, urllib.request, urllib.error

USER = os.environ.get("ZENN_USER", "ailmarketing")
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", ".zenn-notified.json")
UA = "Mozilla/5.0 (compatible; zenn-publish-watch/1.0)"


def fetch_articles():
    url = f"https://zenn.dev/api/articles?username={USER}&count=100"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise SystemExit(f"Zenn API HTTP {r.status}")
        return json.load(r)["articles"]


def topics_of(slug):
    """topics は一覧APIに無いので、同期元のリポジトリから読む。"""
    path = os.path.join(os.path.dirname(__file__), "..", "articles", f"{slug}.md")
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.startswith("topics:"):
                    return ", ".join(
                        t for t in line.split("[", 1)[-1].rstrip("]\n ").replace('"', "").split(", ") if t
                    )
    except OSError:
        pass
    return ""


def post_chatwork(body):
    token = os.environ.get("CHATWORK_API_TOKEN")
    room = os.environ.get("CHATWORK_ROOM_ID")
    if not token or not room:
        # 未設定を成功に丸めない。設定漏れは失敗として出す。
        raise SystemExit("CHATWORK_API_TOKEN / CHATWORK_ROOM_ID が未設定")
    data = urllib.parse.urlencode({"body": body}).encode()
    req = urllib.request.Request(
        f"https://api.chatwork.com/v2/rooms/{room}/messages",
        data=data,
        headers={"X-ChatWorkToken": token,
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def message(a):
    """報告の体裁は macmini の tools/report_public.py に合わせる。
    公開報告は1部屋(447062678)に集約する方針なので、書式が混ざらないようにする。"""
    topics = topics_of(a["slug"])
    lines = ["[info][title]Zenn を公開しました[/title]", a["title"], f"https://zenn.dev{a['path']}"]
    lines.append(f"実績: {a['body_letters_count']:,}字 / {a['article_type']}")
    if topics:
        lines += ["", f"topics: {topics}"]
    lines += ["", f"公開 {a['published_at'][:16].replace('T', ' ')}", "[/info]"]
    return "\n".join(lines)


def main():
    dry = "--dry-run" in sys.argv
    # 設定漏れは「公開が起きた日」まで隠れる。起動時に落として即座に見えるようにする。
    if not dry and not (os.environ.get("CHATWORK_API_TOKEN") and os.environ.get("CHATWORK_ROOM_ID")):
        print("CHATWORK_API_TOKEN / CHATWORK_ROOM_ID が未設定", file=sys.stderr)
        return 2
    articles = fetch_articles()
    with open(STATE_PATH, encoding="utf-8") as f:
        notified = set(json.load(f)["notified"])

    new = [a for a in articles if a["slug"] not in notified]
    new.sort(key=lambda a: a["published_at"])
    print(f"Zenn公開 {len(articles)}本 / 通知済み {len(notified)}本 / 新規 {len(new)}本")

    if not new:
        return 0

    failed = 0
    for a in new:
        body = message(a)
        if dry:
            print("--- DRY RUN ---\n" + body)
            continue
        try:
            code = post_chatwork(body)
            print(f"送信 OK ({code}): {a['slug']}")
            notified.add(a["slug"])          # 成功した分だけ記録する
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            print(f"送信 FAIL: {a['slug']}: {e}", file=sys.stderr)
            failed += 1                       # 記録しない = 次回リトライ

    if not dry:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump({"notified": sorted(notified)}, f, ensure_ascii=False, indent=1)
            f.write("\n")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
