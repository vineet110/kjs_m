import re, html, sys, os, urllib.request, urllib.parse
BASE = "https://kjsindia.com/"
OUT = sys.argv[1]; TXT = sys.argv[2]
pages = ["index.html","stick-pack-factory.html","processing.html","warehousing.html","packaging.html","quality-and-testing.html"]
def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (KJS internal asset export)"})
    with urllib.request.urlopen(req, timeout=30) as r: return r.read()
assets = set(); text_out = []
for p in pages:
    s = get(BASE + p).decode("utf-8", "ignore")
    for m in re.findall(r'(?:src|data-src|data-background|href|poster)=["\']([^"\']+\.(?:png|jpe?g|webp|svg|gif|mp4|webm))', s, re.I): assets.add(urllib.parse.urljoin(BASE + p, m))
    for m in re.findall(r"url\(['\"]?([^)'\"]+)", s): assets.add(urllib.parse.urljoin(BASE + p, m))
    body = re.sub(r'(?s)<(script|style|head)[^>]*>.*?</\1>', '', s)
    body = re.sub(r'(?s)<!--.*?-->', '', body)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', body))
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    text_out.append(f"\n## {p}\n\n" + "\n".join(lines))
css = get(BASE + "assets/css/main.css").decode("utf-8", "ignore")
for m in re.findall(r"url\(['\"]?([^)'\"]+)", css):
    if re.search(r'\.(png|jpe?g|webp|svg|gif)$', m, re.I): assets.add(urllib.parse.urljoin(BASE + "assets/css/main.css", m))
ok = 0
for a in sorted(assets):
    if not a.startswith(BASE): continue
    rel = urllib.parse.unquote(a[len(BASE):]).replace("assets/images/", "")
    if rel.startswith("assets/"): rel = rel[len("assets/"):]
    dest = os.path.join(OUT, rel)
    try:
        data = get(a)
    except Exception as e:
        print("FAIL", a, e); continue
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "wb").write(data); ok += 1
open(TXT, "w", encoding="utf-8").write("# kjsindia.com page text (exported 23 Oct 2026)\n" + "\n".join(text_out))
print("downloaded", ok, "of", len(assets))
