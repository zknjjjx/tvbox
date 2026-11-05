"""CineNest 公共接口汇集（GitHub Actions 每天运行）
从公开的上游列表（gist / 博客 / 配置）和内置种子中提取 CMS 采集接口(api.php/provide/vod)，
去重后写入：
  cmstv.json  —— CineNest 专用接口（CineNest 设置里填它的地址）
  tvbox.json  —— 同一批源的 TVBox 配置（type=1）
不验活：各家网络不同（联通/电信/海外），是否可用由 CineNest 容器在本地测速、播放时自动跳过。
上游暂时消失的源保留 30 天，避免列表抖动。
"""
import asyncio, datetime, hashlib, json, os, re
from urllib.parse import urlparse
import aiohttp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = ROOT
KEEP_DAYS = 30
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

UPSTREAMS = [
    "https://vodtv.github.io/api/",
    "https://gist.githubusercontent.com/lunatickochiya/748774c05c68c0bdf6cd078d88f5112b/raw",
    "https://gist.githubusercontent.com/zyd16888/e186acbadc39a044b61a5361a1d5eb7c/raw",
    "https://gist.githubusercontent.com/gagadesu/de299ec941c940e9596bb5745a24bd6f/raw",
    "https://www.071058.com/index.php/archives/619/",
    "https://github.com/waifu-project/movie/issues/45",
    "https://gist.liushen.fun/LiuShen/backup-moontv-config",
]

SEEDS = {
    "https://cj.lziapi.com/api.php/provide/vod": "量子资源",
    "https://cj.ffzyapi.com/api.php/provide/vod": "非凡资源",
    "https://api.ffzyapi.com/api.php/provide/vod": "非凡资源",
    "https://api.maoyanapi.top/api.php/provide/vod": "猫眼资源",
    "https://www.hongniuzy3.com/api.php/provide/vod": "红牛资源",
    "https://bfzyapi.com/api.php/provide/vod": "暴风资源",
    "https://wolongzyw.com/api.php/provide/vod": "卧龙资源",
    "https://jszyapi.com/api.php/provide/vod": "极速资源",
    "https://api.zuidapi.com/api.php/provide/vod": "最大资源",
    "https://m3u8.apiyhzy.com/api.php/provide/vod": "樱花资源",
    "https://ikunzyapi.com/api.php/provide/vod": "iKun资源",
    "https://www.mdzyapi.com/api.php/provide/vod": "魔都资源",
    "https://caiji.maotaizy.cc/api.php/provide/vod": "茅台资源",
    "https://dbzy.tv/api.php/provide/vod": "豆瓣资源",
    "https://mozhuazy.com/api.php/provide/vod": "魔爪资源",
    "https://wwzy.tv/api.php/provide/vod": "旺旺短剧",
    "https://tyyszyapi.com/api.php/provide/vod": "天涯影视",
    "https://cj.yayazy.net/api.php/provide/vod": "丫丫资源",
    "https://api.guangsuapi.com/api.php/provide/vod": "光速资源",
    "https://360zy.com/api.php/provide/vod": "360资源",
    "https://www.hongniuzy2.com/api.php/provide/vod": "红牛资源",
    "https://sdzyapi.com/api.php/provide/vod": "闪电资源",
    "https://jyzyapi.com/api.php/provide/vod": "金鹰资源",
    "https://api.apibdzy.com/api.php/provide/vod": "百度资源",
    "http://caiji.dyttzyapi.com/api.php/provide/vod": "电影天堂",
    "https://suoniapi.com/api.php/provide/vod": "索尼资源",
    "https://api.ukuapi.com/api.php/provide/vod": "U酷资源",
}

API_RE = re.compile(r"https?://[A-Za-z0-9._-]+(?::\d+)?(?:/[A-Za-z0-9._-]+)*?/api\.php/provide/vod", re.I)
NAME_RE = re.compile(r"""["']?name["']?\s*[:=]\s*["']([^"'\n]{1,30})["']""")
ADULT_WORDS = ["伦理", "福利", "成人", "写真", "三级", "里番", "AV", "无码", "有码", "SM", "色情", "18+", "国产自拍", "强奸", "乱伦", "制服"]




def key_of(api):
    p = urlparse(api)
    return (p.hostname or "").lower().removeprefix("www.") + p.path.lower().rstrip("/")


ADULT_HINTS = ["siwa", "xiangjiao", "91jp", "hsck", "thzy", "lovedan", "heiliao", "xingba", "danaizi",
               "黄色", "色色", "jkun", "lsb", "laoya", "souav", "bttwo", "semao", "xzybb"]


def is_adult(name):
    return any(w.lower() in (name or "").lower() for w in ADULT_WORDS)


def adult_hint(name, api):
    t = (name + " " + (urlparse(api).hostname or "")).lower()
    return is_adult(name) or any(h in t for h in ADULT_HINTS)


def clean_name(name, api):
    name = re.sub(r"^[^\w\u4e00-\u9fff]+", "", (name or "").strip())
    name = re.sub(r"^TV[-_ ]", "", name)
    return name[:20] or (urlparse(api).hostname or api)


async def fetch(session, url):
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=25), headers={"User-Agent": UA}) as r:
        return await r.text(errors="replace")


async def adult_by_classes(session, api, sem):
    """只读分类名判断是否成人站（不判断可用性；读不到就按名字判断）"""
    async with sem:
        try:
            async with session.get(api + "/?ac=list", timeout=aiohttp.ClientTimeout(total=12), headers={"User-Agent": UA}) as r:
                d = json.loads(await r.text(errors="replace"))
            cls = [c.get("type_name", "") for c in d.get("class") or []]
            hits = sum(1 for c in cls if is_adult(c))
            return hits >= 3 or (cls and hits / len(cls) > 0.3)
        except Exception:
            return None


async def main():
    today = datetime.date.today().isoformat()
    os.makedirs(OUT, exist_ok=True)
    prev = {}
    try:
        for s in json.load(open(os.path.join(OUT, "cmstv.json"), encoding="utf-8"))["sites"]:
            prev[key_of(s["api"])] = s
    except Exception:
        pass
    found = {}
    for api, name in SEEDS.items():
        found.setdefault(key_of(api), {"api": api.rstrip("/"), "name": name})
    stats, hot = {}, {}
    for api in SEEDS:
        hot[key_of(api)] = 1  # 知名老站起步 +1
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        texts = await asyncio.gather(*[fetch(session, u) for u in UPSTREAMS], return_exceptions=True)
    for u, text in zip(UPSTREAMS, texts):
        if isinstance(text, Exception):
            stats[u] = "error: " + type(text).__name__
            continue
        n, seen_here = 0, set()
        for m in API_RE.finditer(text):
            api = m.group(0).rstrip("/")
            k = key_of(api)
            if k not in seen_here:
                seen_here.add(k); hot[k] = hot.get(k, 0) + 1  # 人气：被多少个上游收录
            lb, rb = text.rfind("{", 0, m.start()), text.find("}", m.end())
            name = ""
            if lb != -1 and rb != -1 and rb - lb < 600 and "{" not in text[m.end():rb]:
                nm = NAME_RE.findall(text[lb:rb]); name = nm[0] if nm else ""
            if not name:
                nm = NAME_RE.findall(text[max(0, m.start() - 200):m.start()]); name = nm[-1] if nm else ""
            if k not in found:
                found[k] = {"api": api, "name": clean_name(name, api)}; n += 1
            elif name and found[k]["name"] == urlparse(found[k]["api"]).hostname:
                found[k]["name"] = clean_name(name, api)
        stats[u] = n
    sites = {}
    for k, s in found.items():
        old = prev.get(k, {})
        sites[k] = {"name": old.get("name") if old.get("name") and old["name"] != urlparse(s["api"]).hostname else s["name"],
                    "api": s["api"], "adult": adult_hint(s["name"], s["api"]), "first": old.get("first", today), "seen": today, "hot": hot.get(k, 0)}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False, limit=30)) as session:
        sem = asyncio.Semaphore(20)
        ks = list(sites)
        res = await asyncio.gather(*[adult_by_classes(session, sites[k]["api"], sem) for k in ks])
    for k, a in zip(ks, res):
        if a is not None:
            sites[k]["adult"] = bool(a) or sites[k]["adult"]
        elif prev.get(k, {}).get("adult"):
            sites[k]["adult"] = True
    cutoff = (datetime.date.today() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
    for k, s in prev.items():
        if k not in sites and s.get("seen", today) >= cutoff:
            sites[k] = s
    # 同名不同站：加域名区分
    # 按人气排序：被收录的上游越多越靠前
    lst = sorted(sites.values(), key=lambda s: (s["adult"], -s.get("hot", 0), s["first"], s["name"]))
    cnt = {}
    for s in lst:
        cnt[s["name"]] = cnt.get(s["name"], 0) + 1
    for s in lst:
        if cnt[s["name"]] > 1 and "·" not in s["name"]:
            s["name"] = f'{s["name"]}·{(urlparse(s["api"]).hostname or "").removeprefix("www.").split(".")[0]}'
    cms = {"name": "CineNest 公共接口", "format": "cmstv/1",
           "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "count": len(lst), "note": "未验活，按人气（被多少个上游收录）排序；播放时自动跳过不通的源",
           "sites": lst}
    tvb = {"sites": [{"key": "cn_" + hashlib.md5(s["api"].encode()).hexdigest()[:8], "name": s["name"], "type": 1,
                      "api": s["api"] + "/", "searchable": 1, "quickSearch": 1, "filterable": 1}
                     for s in lst if not s["adult"]],
           "parses": [], "lives": [], "notice": f"CineNest 公共接口 · {len(lst)} 个源"}
    json.dump(cms, open(os.path.join(OUT, "cmstv.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(tvb, open(os.path.join(OUT, "tvbox.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("上游", json.dumps(stats, ensure_ascii=False))
    print("合计", len(lst), "其中成人", sum(s["adult"] for s in lst))


if __name__ == "__main__":
    asyncio.run(main())
