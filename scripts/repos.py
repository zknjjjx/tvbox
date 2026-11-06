"""汇聚高人气 TVBox 单仓接口（饭太硬、王二小、肥猫等）+ cmstv.json 里的 CMS 源，生成：
- tvbox.json：单仓合并版（每个站点带自己仓库的 jar，名称前加仓库名）
- multi.json：多仓版（影视仓等支持多仓的软件可用，切换仓库即可）
- upstream/<名>.json：每个仓库最近一次成功拉取的明文，拉取失败时用它兜底
不测速、不过滤，按下面 REPOS 的顺序（人气）排列。
"""
import asyncio, base64, hashlib, json, os, re
from urllib.parse import urljoin
import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "upstream")
UA = {"User-Agent": "okhttp/3.12.13"}

# (简称, [主地址, 备用地址...])，按人气排序；简称会加在站点名前
REPOS = [
    ("饭太硬", ["http://www.饭太硬.com/tv", "http://www.饭太硬.net/tv", "http://fty.888484.xyz/tv", "http://fty.xxooo.cf/tv"]),
    ("肥猫", ["http://肥猫.com/", "http://肥猫.net/", "http://hello.肥猫.com/", "https://6296.kstore.vip/fm.gif"]),
    ("王二小", ["http://tvbox.王二小放牛娃.top/", "https://9280.kstore.vip/newwex.json", "https://9280.kstore.vip/wex.json", "http://tv.999888987.xyz/"]),
    ("摸鱼儿", ["http://我不是.摸鱼儿.com", "http://我不是.摸鱼儿.top", "http://fish.y456y.com"]),
    ("南风", ["https://raw.githubusercontent.com/yoursmile66/TVBox/main/XC.json"]),
    ("菜妮丝", ["https://tv.菜妮丝.top"]),
    ("OK", ["http://ok321.top/tv", "http://ok213.top/tv"]),
    ("巧技", ["http://cdn.qiaoji8.com/tvbox.json"]),
    ("俊佬", ["http://home.jundie.top:81/top98.json"]),
    ("小米", ["https://mitvbox.xyz/小米/DEMO.json", "http://miqk.cc/小米/DEMO.json", "https://mpanso.me/DEMO.json"]),
    ("香雅情", ["https://raw.githubusercontent.com/xyq254245/xyqonlinerule/main/XYQTVBox.json"]),
    ("老刘备", ["https://raw.liucn.cc/box/m.json"]),
    ("小盒子", ["http://xhztv.top/xhz", "http://xhztv.top/4k.json"]),
    ("二月红", ["https://700sjro44343.vicp.fun/eggp/0211/tv.json"]),
    ("宝盒", ["https://raw.githubusercontent.com/guot55/YGBH/main/vip2.json"]),
    ("高天流云", ["https://raw.githubusercontent.com/gaotianliuyun/gao/master/js.json"]),
    ("dxawi", ["https://dxawi.github.io/0/0.json"]),
]


# 单仓合并版只并入人气最高的前几个仓库（站点太多电视会卡、全局搜索很慢）；其余都在 multi.json 里
MERGE_TOP = int(os.environ.get("MERGE_TOP", "6"))


BRAND = "妞妞"
CDN = "https://cdn.jsdelivr.net/gh/zknjjjx/tvbox@main"
SEP = re.compile(r"[┃┆|丨│｜]+")
AD = re.compile(r"QQ|频道|公众号|微信|群|关注|禁止|贩卖|免费分享|宝贝|请勿|广告|更新|日期|^APP$|放牛娃|饭太硬|肥猫|摸鱼|南风|菜妮丝")
# 需要登录网盘或只是设置/推送工具的站点不收
SKIP = re.compile(r"网盘|云盘|盘搜|盘她|盘他|配置|设置|本地|推送|夸克|百度|阿里|天翼|115|PikPak|优熙|我的|媒体库|Push|Config|Local|PanSou|PanSo|YpanSo|BpanSo|Drive|Woucpan|WoBaidu", re.I)


def clean_name(n):
    parts = []
    for p in SEP.split(n or ""):
        p = re.sub(r"[^\w\u4e00-\u9fff+\-·.]", "", p).strip("._-·")
        if p and not AD.search(p):
            parts.append(p)
    return parts


# ---------- 解码：明文 / 图片尾部 base64 / 2423 开头的 AES-CBC ----------
def _pad16(s):
    return (s + "0" * 16)[:16]


def _cbc(data):
    raw = bytes.fromhex(data).decode("latin1").lower()
    key = _pad16(raw[raw.index("$#") + 2:raw.index("#$")])
    iv = _pad16(raw[-13:])
    body = bytes.fromhex(data[data.index("2324") + 4:len(data) - 26])
    d = Cipher(algorithms.AES(key.encode()), modes.CBC(iv.encode())).decryptor()
    out = d.update(body) + d.finalize()
    return out[:-out[-1]].decode("utf-8", "ignore")


def decode(b):
    t = b.decode("utf-8", "ignore").strip().lstrip("\ufeff")
    if t.startswith("2423"):
        return _cbc(t)
    m = re.search(r"[A-Za-z0-9]{8}\*\*", t)
    if m and not t.lstrip("/ \n").startswith("{"):
        s = re.sub(r"\s", "", t[m.end():])
        t = base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")
        if t.strip().startswith("2423"):
            return _cbc(t.strip())
    return t


def loose_json(t):
    """去掉 // 和 /* */ 注释、尾逗号后解析（不动字符串里的内容）"""
    out, i, n, ins = [], 0, len(t), False
    while i < n:
        c = t[i]
        if ins:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(t[i + 1]); i += 2; continue
            if c == '"':
                ins = False
            i += 1; continue
        if c == '"':
            ins = True; out.append(c); i += 1; continue
        if t.startswith("//", i):
            j = t.find("\n", i); i = n if j == -1 else j; continue
        if t.startswith("/*", i):
            j = t.find("*/", i + 2); i = n if j == -1 else j + 2; continue
        out.append(c); i += 1
    s = re.sub(r",(\s*[}\]])", r"\1", "".join(out))
    s = s[s.find("{"):]
    return json.loads(s)


async def fetch_repo(session, name, urls):
    for u in urls:
        try:
            async with session.get(u, timeout=aiohttp.ClientTimeout(total=25), headers=UA, allow_redirects=True) as r:
                b = await r.read()
                final = str(r.url)
            d = loose_json(decode(b))
            if d.get("sites"):
                return name, u, final, d
        except Exception as e:
            print(f"  {name} {u} 失败：{type(e).__name__}")
    return name, None, None, None


def absu(v, base):
    """把 ./xx、../xx 相对地址转成绝对地址（保留 ;md5;xxx 后缀）"""
    if not isinstance(v, str) or not base:
        return v
    if v.startswith("./") or v.startswith("../"):
        head, sep, tail = v.partition(";")
        return urljoin(base, head) + sep + tail
    return v


async def main():
    os.makedirs(CACHE, exist_ok=True)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=20)) as session:
        res = await asyncio.gather(*[fetch_repo(session, n, us) for n, us in REPOS])

    sites, parses, lives, rules, flags, ads, multi = [], [], [], [], [], [], []
    seen_site, seen_parse, seen_live = set(), set(), set()
    first = {}
    report = {}
    for name, url, final, d in res:
        cache = os.path.join(CACHE, f"{name}.json")
        if d:
            json.dump({"url": url, "final": final, "conf": d}, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
            report[name] = f"ok {len(d['sites'])}"
        elif os.path.exists(cache):
            c = json.load(open(cache, encoding="utf-8"))
            url, final, d = c["url"], c["final"], c["conf"]
            report[name] = f"用缓存 {len(d['sites'])}"
        else:
            report[name] = "失败"
            continue
        multi.append({"name": name, "url": url})
        if len(multi) > MERGE_TOP:
            continue
        base = final or url
        spider = absu(d.get("spider", ""), base)
        for k in ("doh", "ijk", "wallpaper", "logo"):
            if d.get(k) and k not in first:
                first[k] = d[k]
        if spider and "spider" not in first:
            first["spider"] = spider
        for s in d["sites"]:
            if not isinstance(s, dict) or not s.get("api"):
                continue
            s = dict(s)
            for k in ("api", "ext", "jar", "playUrl"):
                if k in s:
                    s[k] = absu(s[k], base)
            if s.get("jar"):
                s["jar"] = absu(s["jar"], base)
            elif spider and (str(s.get("type")) == "3" or str(s["api"]).startswith("csp_")):
                s["jar"] = spider
            parts = clean_name(s.get("name"))
            if not parts or SKIP.search(s.get("name") or "") or SKIP.search(str(s["api"])):
                continue
            core = parts[0]
            if core in seen_site:  # 同名站点只留人气最高仓库的那个
                continue
            seen_site.add(core)
            s["key"] = f"{name}_{s.get('key') or s.get('name')}"
            s["name"] = "┃".join(parts[:2])
            sites.append(s)
        for p in d.get("parses") or []:
            if isinstance(p, dict) and p.get("url") and p["url"] not in seen_parse and not p["url"].startswith("Demo"):
                seen_parse.add(p["url"]); p = dict(p); p["url"] = absu(p["url"], base); parses.append(p)
        for lv in d.get("lives") or []:
            if not isinstance(lv, dict):
                continue
            key = lv.get("url") or lv.get("api") or json.dumps(lv, ensure_ascii=False, sort_keys=True)
            if key in seen_live:
                continue
            seen_live.add(key); lv = dict(lv)
            for k in ("url", "api", "epg", "logo", "jar"):
                if k in lv:
                    lv[k] = absu(lv[k], base)
            lv["name"] = "┃".join(clean_name(lv.get("name")) or ["直播"]) + f"·{len(lives) + 1}"
            lives.append(lv)
        rules += d.get("rules") or []
        for f in d.get("flags") or []:
            if f not in flags:
                flags.append(f)
        for a in d.get("ads") or []:
            if a not in ads:
                ads.append(a)

    # 再接上 CMS 采集站（成人标记的不放进电视用的配置）
    cms = json.load(open(os.path.join(ROOT, "cmstv.json"), encoding="utf-8"))["sites"]
    for s in cms:
        if s.get("adult"):
            continue
        if s["name"] in seen_site:
            continue
        seen_site.add(s["name"])
        sites.append({"key": "cn_" + hashlib.md5(s["api"].encode()).hexdigest()[:8], "name": f"{s['name']}┃采集",
                      "type": 1, "api": s["api"] + "/", "searchable": 1, "quickSearch": 1, "filterable": 1})

    # 父解析：保留一个 Web 解析在前
    import datetime
    out = {"spider": first.get("spider", ""), "wallpaper": f"{CDN}/assets/wallpaper.jpg", "logo": f"{CDN}/assets/logo.png",
           "sites": sites, "parses": parses, "lives": lives, "rules": rules, "flags": flags, "ads": ads,
           "notice": f"{BRAND} · {len(sites)} 个站点 · 每日更新 {datetime.date.today().isoformat()}"}
    if first.get("doh"):
        out["doh"] = first["doh"]
    if first.get("ijk"):
        out["ijk"] = first["ijk"]
    for fn in ("niuniu.json", "tvbox.json"):  # tvbox.json 保留同样内容，兼容旧地址
        json.dump(out, open(os.path.join(ROOT, fn), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"urls": [{"name": BRAND, "url": f"{CDN}/niuniu.json"}] + multi},
              open(os.path.join(ROOT, "multi.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("仓库", json.dumps(report, ensure_ascii=False))
    print("合计站点", len(sites), "解析", len(parses), "直播", len(lives))


if __name__ == "__main__":
    asyncio.run(main())
