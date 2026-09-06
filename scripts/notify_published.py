#!/usr/bin/env python3
"""実際に公開された記事だけを Chatwork「公開報告」部屋(447062678)へ報告する。

なぜ push を見ないか: 記事パイプラインは `git push` が成功した時点で success:true と
URL を返すが、Zenn の公開は先入れ先出しで実測 2.6日に1本しか進まない。
push 直後の URL は 404 なので、それを通知すると存在しないURLを配ることになる。
(実測 2026-09-06: slug 20260727 の記事が同日 08:19 に公開 = 41日遅れ)
Qiita は即時公開なので同じ仕組みでも遅延なく出る。

報告の体裁は macmini の ~/youtube-ai-pipeline/tools/report_public.py に合わせている。
公開報告は1部屋に集約する方針(2026-09-05 指示)なので、書式を混ぜない。

状態: .published-notified.json。通知に成功した id だけ記録する = 失敗分は次回リトライ。
"""
import json, os, sys, urllib.parse, urllib.request, urllib.error

ROOT = os.path.join(os.path.dirname(__file__), "..")
STATE_PATH = os.path.join(ROOT, ".published-notified.json")
UA = "Mozilla/5.0 (compatible; publish-watch/1.0)"
ZENN_USER = os.environ.get("ZENN_USER", "ailmarketing")
QIITA_USER = os.environ.get("QIITA_USER", "sescore")
NOTE_USER = os.environ.get("NOTE_USER", "sescore")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        if r.status != 200:
            raise SystemExit(f"{url} → HTTP {r.status}")
        return json.load(r)


def zenn_topics(slug):
    """topics は一覧APIに無いので、同期元のリポジトリから読む。"""
    try:
        with open(os.path.join(ROOT, "articles", f"{slug}.md"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("topics:"):
                    raw = line.split("[", 1)[-1].rstrip("]\n ").replace('"', "")
                    return ", ".join(t for t in raw.split(", ") if t)
    except OSError:
        pass
    return ""


def fetch_zenn():
    out = []
    for a in get_json(f"https://zenn.dev/api/articles?username={ZENN_USER}&count=100")["articles"]:
        out.append({
            "id": a["slug"],
            "kind": "Zenn",
            "title": a["title"],
            "url": f"https://zenn.dev{a['path']}",
            "metric": f"{a['body_letters_count']:,}字 / {a['article_type']}",
            "note": f"topics: {zenn_topics(a['slug'])}" if zenn_topics(a["slug"]) else "",
            "at": a["published_at"][:16].replace("T", " "),
        })
    return out


def fetch_qiita():
    out = []
    for a in get_json(f"https://qiita.com/api/v2/users/{QIITA_USER}/items?per_page=100"):
        if a.get("private"):
            continue
        tags = ", ".join(t["name"] for t in a.get("tags", []))
        out.append({
            "id": a["id"],
            "kind": "Qiita",
            "title": a["title"],
            "url": a["url"],
            "metric": f"LGTM {a.get('likes_count', 0)} / ストック {a.get('stocks_count', 0)}",
            "note": f"tags: {tags}" if tags else "",
            "at": a["created_at"][:16].replace("T", " "),
        })
    return out


def fetch_note():
    """note も公開APIで取れる(認証不要)。ページングして全件見る。"""
    out, page = [], 1
    while page <= 25:
        d = get_json(f"https://note.com/api/v2/creators/{NOTE_USER}/contents?kind=note&page={page}")["data"]
        for a in d.get("contents", []):
            out.append({
                "id": str(a.get("id") or a.get("key")),
                "kind": "note",
                "title": a.get("name") or "",
                "url": f"https://note.com/{NOTE_USER}/n/{a.get('key')}",
                "metric": f"スキ {a.get('likeCount', 0)}",
                "note": "",
                "at": (a.get("publishAt") or "")[:16].replace("T", " "),
            })
        if d.get("isLastPage"):
            break
        page += 1
    return out


def message(a):
    lines = [f"[info][title]{a['kind']} を公開しました[/title]", a["title"], a["url"],
             f"実績: {a['metric']}"]
    if a["note"]:
        lines += ["", a["note"]]
    lines += ["", f"公開 {a['at']}", "[/info]"]
    return "\n".join(lines)


def post_chatwork(body):
    token = os.environ["CHATWORK_API_TOKEN"]
    room = os.environ["CHATWORK_ROOM_ID"]
    data = urllib.parse.urlencode({"body": body}).encode()
    req = urllib.request.Request(
        f"https://api.chatwork.com/v2/rooms/{room}/messages", data=data,
        headers={"X-ChatWorkToken": token,
                 "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def main():
    dry = "--dry-run" in sys.argv
    # 設定漏れは「公開が起きた日」まで隠れる。起動時に落として即座に見えるようにする。
    if not dry and not (os.environ.get("CHATWORK_API_TOKEN") and os.environ.get("CHATWORK_ROOM_ID")):
        print("CHATWORK_API_TOKEN / CHATWORK_ROOM_ID が未設定", file=sys.stderr)
        return 2

    with open(STATE_PATH, encoding="utf-8") as f:
        state = json.load(f)

    failed = 0
    for name, fetch in (("zenn", fetch_zenn), ("qiita", fetch_qiita), ("note", fetch_note)):
        try:
            items = fetch()
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            print(f"{name}: 取得FAIL: {e}", file=sys.stderr)
            failed += 1               # 取得失敗を「0件」と数えない
            continue
        done = set(state.get(name, []))
        new = sorted((i for i in items if i["id"] not in done), key=lambda x: x["at"])
        print(f"{name}: 公開{len(items)}本 / 通知済み{len(done)}本 / 新規{len(new)}本")
        for a in new:
            if dry:
                print("--- DRY RUN ---\n" + message(a))
                continue
            try:
                code = post_chatwork(message(a))
                print(f"  送信 OK ({code}): {a['id']}")
                done.add(a["id"])      # 成功した分だけ記録する
            except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
                print(f"  送信 FAIL: {a['id']}: {e}", file=sys.stderr)
                failed += 1            # 記録しない = 次回リトライ
        state[name] = sorted(done)

    if not dry:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)
            f.write("\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
