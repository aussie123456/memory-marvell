#!/usr/bin/env python3
"""Build the Memory & Marvell Desk page.

Steps: inject curated.json into template.html, point the Refresh button at the GitHub Actions
workflow, re-fetch every data block that carries a data-url, back-fill any block whose fetch
failed from the previously published page, stamp d-meta, write the output page.

Usage: python3 build.py [--template template.html] [--curated curated.json]
                        [--previous previous.html] [--out dist/index.html] [--min-ok 1]
Env:   REFRESH_URL  where the page's Refresh button should link (the workflow sets it to the
       Actions page of refresh.yml, where "Run workflow" triggers a manual refresh).
Requires Python 3.8+, stdlib only. The fetch logic mirrors the refresh script embedded in the page.
"""
import re, os, sys, json, html, time, argparse, datetime, urllib.request, urllib.parse, http.cookiejar

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
SEC_UA = "memory-marvell-desk research dashboard"
END = "</" + "script>"
# Every real data block starts at column 0; the ^ anchor keeps the same literals inside the
# embedded Python script in the template untouched.
BLOCK = re.compile(r'^(<script type="application/json" id="(d-[\w-]+)"([^>]*)>)(.*?)(' + re.escape(END) + ')', re.S | re.M)


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, opener=None, ua=UA, timeout=40):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
    op = opener or urllib.request.build_opener()
    with op.open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def yahoo_session():
    for attempt in range(4):
        try:
            cj = http.cookiejar.CookieJar()
            op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            try:
                get("https://fc.yahoo.com", op, timeout=20)
            except Exception:
                pass
            crumb = get("https://query2.finance.yahoo.com/v1/test/getcrumb", op, timeout=20).strip()
            if crumb and len(crumb) < 30 and "{" not in crumb and " " not in crumb:
                return op, crumb
        except Exception:
            pass
        time.sleep(3 + attempt * 4)
    return None, None


def escape_payload(s):
    return s.replace("</", "<\\/")


def set_block(text, bid, payload):
    """Replace the payload of one top-level data block (used for d-curated and d-meta)."""
    pat = re.compile(r'^(<script type="application/json" id="' + re.escape(bid) + r'"[^>]*>)(.*?)(' + re.escape(END) + ')', re.S | re.M)
    return pat.sub(lambda m: m.group(1) + escape_payload(payload) + m.group(3), text, count=1)


def previous_blocks(path):
    """Map block id -> (attrs, payload) from a previously built page, or {} if unavailable."""
    out = {}
    if not path or not os.path.exists(path):
        return out
    try:
        prev = open(path, encoding="utf-8").read()
    except Exception:
        return out
    if 'id="d-meta"' not in prev:
        return out
    for m in BLOCK.finditer(prev):
        out[m.group(2)] = (m.group(3), m.group(4))
    return out


def point_refresh_button(text, url):
    """Repoint the header Refresh button (and its explanatory text) at the GitHub workflow."""
    text = re.sub(r'(class="refresh-btn" href=")[^"]*(")', lambda m: m.group(1) + html.escape(url, quote=True) + m.group(2), text, count=1)
    text = re.sub(r'(class="refresh-btn"[^>]*title=")[^"]*(")',
                  lambda m: m.group(1) + "Opens the GitHub Actions workflow; press Run workflow. New data appears here in 3 to 5 minutes." + m.group(2),
                  text, count=1)
    text = text.replace("The Refresh data button opens the refresh job; pressing Run there",
                        "The Refresh data button opens the GitHub Actions workflow; pressing Run workflow there")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="template.html")
    ap.add_argument("--curated", default="curated.json")
    ap.add_argument("--previous", default="previous.html")
    ap.add_argument("--out", default=os.path.join("dist", "index.html"))
    ap.add_argument("--min-ok", type=int, default=1, help="fail unless at least this many blocks were fetched or back-filled")
    a = ap.parse_args()

    text = open(a.template, encoding="utf-8").read()

    # 1. curated data
    cur = open(a.curated, encoding="utf-8").read()
    json.loads(cur)  # validate
    text = set_block(text, "d-curated", cur)

    # 2. refresh button
    refresh_url = os.environ.get("REFRESH_URL", "").strip()
    if refresh_url:
        text = point_refresh_button(text, refresh_url)

    # 3. previous page for back-fill
    prev = previous_blocks(a.previous)
    print("previous page: %s" % ("%d blocks" % len(prev) if prev else "none"))

    # 4. fetch
    status = {}
    yop = ycrumb = None
    if 'data-auth="yahoo"' in text:
        yop, ycrumb = yahoo_session()
        print("yahoo crumb: %s" % ("ok" if ycrumb else "FAILED"))

    def repl(m):
        open_tag, bid, attrs, old, close = m.groups()
        murl = re.search(r'data-url="([^"]+)"', attrs)
        if not murl:
            return m.group(0)
        url = html.unescape(murl.group(1))
        kind = (re.search(r'data-kind="(\w+)"', attrs) or [None, "json"])[1]
        auth = (re.search(r'data-auth="(\w+)"', attrs) or [None, ""])[1]
        ua = SEC_UA if 'data-ua="sec"' in attrs else UA
        payload = None
        err = None
        for attempt in range(3):
            try:
                if auth == "yahoo":
                    if not ycrumb:
                        raise RuntimeError("no yahoo crumb")
                    body = get(url.replace("{crumb}", urllib.parse.quote(ycrumb)), yop, ua)
                else:
                    body = get(url, None, ua)
                if kind == "json":
                    obj = json.loads(body)
                    payload = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
                else:
                    if len(body) < 50:
                        raise RuntimeError("short body")
                    if "news.google.com" in url:
                        body = re.sub(r"<description>.*?</description>", "", body, flags=re.S)
                    payload = json.dumps(body, ensure_ascii=False)
                break
            except Exception as e:
                err = str(e)[:120]
                time.sleep(2 + attempt * 3)
        attrs2 = re.sub(r'\s*data-fetched="[^"]*"', "", attrs)
        if payload is not None:
            status[bid] = "ok"
            print("  %-18s ok   %s chars" % (bid, format(len(payload), ",")))
            return '<script type="application/json" id="%s"%s data-fetched="%s">%s%s' % (bid, attrs2, now_iso(), escape_payload(payload), close)
        # fetch failed: keep the previously published payload if there is one
        pattrs, ppayload = prev.get(bid, ("", ""))
        if ppayload.strip() not in ("", "null"):
            fetched = re.search(r'data-fetched="([^"]*)"', pattrs)
            stamp = fetched.group(1) if fetched else ""
            status[bid] = "error: %s (kept previous)" % (err or "unknown")
            print("  %-18s FAIL %s (kept previous from %s)" % (bid, err, stamp or "?"))
            return '<script type="application/json" id="%s"%s data-fetched="%s">%s%s' % (bid, attrs2, stamp, ppayload, close)
        status[bid] = "error: " + (err or "unknown")
        print("  %-18s FAIL %s" % (bid, err))
        return m.group(0)

    text = BLOCK.sub(repl, text)

    # 5. meta
    meta = {"generated_at": now_iso(), "status": status, "builder": "github-actions" if os.environ.get("GITHUB_ACTIONS") else "local"}
    text = set_block(text, "d-meta", json.dumps(meta))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(text)

    ok = sum(1 for v in status.values() if v == "ok")
    kept = sum(1 for v in status.values() if "kept previous" in v)
    print("wrote %s (%s bytes); %d/%d blocks refreshed, %d kept previous" % (a.out, format(len(text.encode("utf-8")), ","), ok, len(status), kept))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## IREN Markets Desk refresh\n\n%d/%d blocks refreshed, %d kept previous, generated %s\n\n| Block | Status |\n|---|---|\n" % (ok, len(status), kept, meta["generated_at"]))
            for k, v in status.items():
                f.write("| %s | %s |\n" % (k, v))

    if ok + kept < a.min_ok:
        print("FAIL: only %d blocks have data (min-ok %d); not publishing an empty page" % (ok + kept, a.min_ok))
        sys.exit(1)


if __name__ == "__main__":
    main()
