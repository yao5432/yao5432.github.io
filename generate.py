#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日自动生成 · iOS 风格 AI 资讯网站 (GitHub Pages 适用)
---------------------------------------------------
数据来源（无需 API Key）：
  - Hacker News  (Algolia 搜索接口)
  - arXiv        (cs.AI / cs.CL / cs.LG 最新投稿, Atom 接口)
  - 科技媒体 RSS (The Verge / Ars Technica / Wired 等, 可选 feedparser)

运行： python generate.py  ->  生成 index.html
GitHub Actions 每日定时运行本脚本并提交，GitHub Pages 即自动更新。
"""

import os
import sys
import json
import html
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta

# ----------------------------- 配置 -----------------------------
HN_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "LLM",
    "GPT", "OpenAI", "deep learning", "neural network", "transformer",
    "large language model", "diffusion model", "AI agent", "Claude", "Gemini",
]
HN_PER_KW = 10
HN_TOTAL = 14
ARXIV_MAX = 8
RSS_MAX_PER = 4
RSS_FEEDS = [
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica", "http://feeds.arstechnica.com/arstechnica/index"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]
UA = {"User-Agent": "Mozilla/5.0 (compatible; AI-News-Daily/1.0)"}


# ----------------------------- 抓取工具 -----------------------------
def fetch_json(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_text(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)          # 去 HTML 标签
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_time(s):
    if not s:
        return None
    s = s.strip()
    fmts = (
        "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S.%f%z",
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
    )
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ----------------------------- 各数据源 -----------------------------
def fetch_hn():
    items = {}
    for kw in HN_KEYWORDS:
        try:
            q = urllib.parse.quote(kw)
            url = (f"https://hn.algolia.com/api/v1/search_by_date?query={q}"
                   f"&tags=story&hitsPerPage={HN_PER_KW}")
            data = fetch_json(url)
            for h in data.get("hits", []):
                oid = h.get("objectID")
                if not oid or oid in items:
                    continue
                title = h.get("title") or h.get("story_title")
                if not title:
                    continue
                link = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
                items[oid] = {
                    "title": clean(title),
                    "summary": "",
                    "url": link,
                    "source": "Hacker News",
                    "source_type": "news",
                    "points": h.get("points") or 0,
                    "comments": h.get("num_comments") or 0,
                    "author": h.get("author") or "",
                    "published": h.get("created_at"),
                }
        except Exception as e:
            print(f"  [HN] 关键词 '{kw}' 抓取失败: {e}", file=sys.stderr)
    lst = list(items.values())
    lst.sort(key=lambda x: (x["points"] or 0), reverse=True)
    return lst[:HN_TOTAL]


def fetch_arxiv():
    try:
        url = ("http://export.arxiv.org/api/query?search_query=cat:cs.AI"
               "+OR+cat:cs.CL+OR+cat:cs.LG"
               f"&sortBy=submittedDate&sortOrder=descending&max_results={ARXIV_MAX}")
        xml = fetch_text(url)
        import xml.etree.ElementTree as ET
        ns = {"a": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(xml)
        out = []
        for e in root.findall("a:entry", ns):
            title = clean(e.findtext("a:title", namespaces=ns))
            summary = clean(e.findtext("a:summary", namespaces=ns))
            published = e.findtext("a:published", namespaces=ns)
            link = e.findtext("a:id", namespaces=ns)
            authors = [a.findtext("a:name", namespaces=ns)
                       for a in e.findall("a:author", ns)][:3]
            out.append({
                "title": title,
                "summary": summary,
                "url": link,
                "source": "arXiv",
                "source_type": "paper",
                "points": 0,
                "comments": 0,
                "author": ", ".join([a for a in authors if a]),
                "published": published,
            })
        return out
    except Exception as e:
        print(f"  [arXiv] 抓取失败: {e}", file=sys.stderr)
        return []


def fetch_rss():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过媒体源", file=sys.stderr)
        return []
    out = []
    for name, url in RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:RSS_MAX_PER]:
                out.append({
                    "title": clean(e.get("title", "")),
                    "summary": clean(e.get("summary") or e.get("description") or ""),
                    "url": e.get("link", ""),
                    "source": name,
                    "source_type": "media",
                    "points": 0,
                    "comments": 0,
                    "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS] {name} 抓取失败: {ex}", file=sys.stderr)
    return out


# ----------------------------- 离线兜底数据 -----------------------------
SAMPLE = [
    {
        "title": "示例：OpenAI 发布新一代多模态推理模型",
        "summary": "（这是离线兜底示例。部署到 GitHub 后，GitHub Actions 会每天抓取真实的 Hacker News / arXiv / 科技媒体资讯并自动更新本页。）",
        "url": "https://github.com",
        "source": "Hacker News", "source_type": "news",
        "points": 1280, "comments": 342, "author": "demo",
        "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    {
        "title": "示例：arXiv 论文 — 高效稀疏注意力机制综述",
        "summary": "A survey on efficient sparse attention for long-context large language models. （离线示例数据）",
        "url": "https://arxiv.org", "source": "arXiv", "source_type": "paper",
        "points": 0, "comments": 0, "author": "Demo Authors",
        "published": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
    },
    {
        "title": "示例：科技媒体报道 AI 芯片竞争格局变化",
        "summary": "行业观察：新入局者正在重塑 AI 加速器的供应格局。（离线示例数据）",
        "url": "https://example.com", "source": "The Verge AI", "source_type": "media",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat(),
    },
]


# ----------------------------- 主流程 -----------------------------
def main():
    print("→ 正在抓取 AI 资讯 ...")
    items = []
    items += fetch_hn()
    items += fetch_arxiv()
    items += fetch_rss()

    if not items:
        print("! 所有在线源均不可用，使用离线兜底数据生成预览。", file=sys.stderr)
        items = SAMPLE

    for it in items:
        it["_dt"] = parse_time(it["published"])
    items.sort(key=lambda x: x["_dt"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    items = [{k: v for k, v in it.items() if k != "_dt"} for it in items]

    data = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "count": len(items),
        "items": items,
    }

    # 序列化时转义 < > &，避免破坏 <script>
    safe = (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    out_html = HTML_TEMPLATE.replace("__DATA_JSON__", safe)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"✓ 已生成 index.html（共 {len(items)} 条资讯）")


# ----------------------------- 页面模板 (iOS 风格) -----------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#f2f2f7" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)" />
<title>AI 资讯日报</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%23007aff'/%3E%3Ctext x='50' y='68' font-size='54' font-family='Arial' font-weight='700' fill='white' text-anchor='middle'%3EAI%3C/text%3E%3C/svg%3E" />
<style>
  :root{
    --bg:#f2f2f7; --card:#ffffff; --text:#1c1c1e; --sub:#8e8e93;
    --line:rgba(60,60,67,.12); --accent:#007aff; --accent-soft:rgba(0,122,255,.12);
    --news:#ff9500; --paper:#5e5ce6; --media:#34c759;
    --shadow:0 1px 2px rgba(0,0,0,.06),0 10px 30px rgba(0,0,0,.07);
    --radius:20px;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#000; --card:#1c1c1e; --text:#f2f2f7; --sub:#98989f;
      --line:rgba(255,255,255,.12); --accent-soft:rgba(10,132,255,.18);
      --shadow:0 1px 2px rgba(0,0,0,.5),0 12px 32px rgba(0,0,0,.45);
    }
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent;}
  html,body{margin:0;padding:0;}
  body{
    background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display",
      "Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
    line-height:1.45; -webkit-font-smoothing:antialiased;
    padding-bottom:48px;
  }
  .wrap{max-width:680px;margin:0 auto;padding:0 16px;}

  /* 毛玻璃导航 */
  .nav{
    position:sticky;top:0;z-index:20;
    backdrop-filter:saturate(180%) blur(20px);
    -webkit-backdrop-filter:saturate(180%) blur(20px);
    background:rgba(242,242,247,.72);
    border-bottom:.5px solid var(--line);
  }
  @media (prefers-color-scheme: dark){ .nav{background:rgba(0,0,0,.72);} }
  .nav-in{max-width:680px;margin:0 auto;padding:10px 16px;
    display:flex;align-items:center;justify-content:space-between;}
  .nav-title{font-weight:700;font-size:17px;letter-spacing:.3px;}
  .nav-up{font-size:12px;color:var(--sub);display:flex;align-items:center;gap:6px;}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--media);
    box-shadow:0 0 0 0 rgba(52,199,89,.6);animation:pulse 2s infinite;}
  @keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,199,89,.5);}70%{box-shadow:0 0 0 7px rgba(52,199,89,0);}100%{box-shadow:0 0 0 0 rgba(52,199,89,0);}}

  /* 头部 */
  .hero{padding:26px 0 12px;}
  .hero h1{
    margin:0;font-size:34px;font-weight:800;letter-spacing:-.5px;
    background:linear-gradient(120deg,#007aff,#5e5ce6 55%,#ff2d55);
    -webkit-background-clip:text;background-clip:text;color:transparent;
  }
  .hero .date{margin-top:4px;color:var(--sub);font-size:14px;}
  .hero .cnt{color:var(--accent);font-weight:600;}

  /* 分段控制器 */
  .seg{
    display:flex;gap:4px;background:var(--accent-soft);
    padding:4px;border-radius:14px;margin:14px 0 18px;
    position:relative;overflow:hidden;
  }
  .seg button{
    flex:1;border:0;background:transparent;color:var(--text);
    font-size:14px;font-weight:600;padding:9px 0;border-radius:10px;
    cursor:pointer;transition:color .25s;font-family:inherit;position:relative;z-index:2;
  }
  .seg button.active{color:var(--text);}
  .seg .pill{
    position:absolute;top:4px;bottom:4px;left:4px;width:calc((100% - 8px)/4 - 0px);
    background:var(--card);border-radius:10px;box-shadow:var(--shadow);
    transition:transform .3s cubic-bezier(.4,1.3,.5,1);z-index:1;
  }
  .seg button.active{color:var(--accent);}

  /* 卡片 */
  .card{
    background:var(--card);border-radius:var(--radius);padding:16px 18px;
    margin-bottom:14px;box-shadow:var(--shadow);cursor:pointer;
    text-decoration:none;color:inherit;display:block;
    transition:transform .18s ease,box-shadow .18s ease;
    animation:rise .5s both;
  }
  .card:hover{transform:translateY(-3px);box-shadow:0 2px 6px rgba(0,0,0,.1),0 16px 40px rgba(0,0,0,.1);}
  @keyframes rise{from{opacity:0;transform:translateY(14px);}to{opacity:1;transform:none;}}
  .card-top{display:flex;align-items:center;gap:8px;margin-bottom:9px;flex-wrap:wrap;}
  .badge{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600;
    padding:3px 9px;border-radius:999px;background:var(--accent-soft);color:var(--accent);}
  .badge .bdot{width:7px;height:7px;border-radius:50%;background:var(--accent);}
  .badge.news{background:rgba(255,149,0,.14);color:var(--news);} .badge.news .bdot{background:var(--news);}
  .badge.paper{background:rgba(94,92,230,.16);color:var(--paper);} .badge.paper .bdot{background:var(--paper);}
  .badge.media{background:rgba(52,199,89,.16);color:var(--media);} .badge.media .bdot{background:var(--media);}
  .time{margin-left:auto;font-size:12px;color:var(--sub);}
  .card h2{margin:0 0 7px;font-size:17px;font-weight:700;line-height:1.35;letter-spacing:-.2px;}
  .card p{margin:0;font-size:14.5px;color:var(--sub);line-height:1.5;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
  .card-foot{margin-top:11px;display:flex;align-items:center;gap:14px;font-size:12.5px;color:var(--sub);}
  .card-foot .go{margin-left:auto;color:var(--accent);font-weight:600;display:inline-flex;align-items:center;gap:3px;}

  .empty{text-align:center;color:var(--sub);padding:60px 20px;font-size:15px;}

  footer{text-align:center;color:var(--sub);font-size:12px;margin-top:26px;line-height:1.7;}
  footer a{color:var(--accent);text-decoration:none;}
</style>
</head>
<body>
  <div class="nav">
    <div class="nav-in">
      <div class="nav-title">AI 资讯日报</div>
      <div class="nav-up"><span class="dot"></span><span id="upd">更新中…</span></div>
    </div>
  </div>

  <div class="wrap">
    <div class="hero">
      <h1>AI 资讯日报</h1>
      <div class="date" id="herodate">—</div>
    </div>

    <div class="seg" id="seg">
      <span class="pill" id="pill"></span>
      <button data-f="all" class="active">全部</button>
      <button data-f="news">资讯</button>
      <button data-f="paper">论文</button>
      <button data-f="media">媒体</button>
    </div>

    <div id="feed"></div>

    <footer>
      由 GitHub Actions 每日自动更新 · 数据来源 Hacker News / arXiv / 科技媒体<br/>
      本页为静态生成，可直接托管于 GitHub Pages
    </footer>
  </div>

<script>
const DATA = __DATA_JSON__;
const WEEK = ["星期日","星期一","星期二","星期三","星期四","星期五","星期六"];

function fmtDate(d){
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 ${WEEK[d.getDay()]}`;
}
function relTime(iso){
  const t = new Date(iso).getTime();
  if (isNaN(t)) return "";
  const s = (Date.now()-t)/1000;
  if (s < 3600) return Math.max(1,Math.floor(s/60)) + " 分钟前";
  if (s < 86400) return Math.floor(s/3600) + " 小时前";
  if (s < 86400*7) return Math.floor(s/86400) + " 天前";
  const d = new Date(t);
  return `${d.getMonth()+1}月${d.getDate()}日`;
}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}

// 导航更新时间
(() => {
  const ga = new Date(DATA.generated_at);
  document.getElementById("upd").textContent =
    "更新于 " + String(ga.getHours()).padStart(2,"0") + ":" + String(ga.getMinutes()).padStart(2,"0");
  const now = new Date();
  document.getElementById("herodate").innerHTML =
    fmtDate(now) + " · 今日收录 <span class='cnt'>" + DATA.count + "</span> 条";
})();

const TYPE_LABEL = {news:"Hacker News", paper:"arXiv", media:"媒体"};
let current = "all";

function render(){
  const feed = document.getElementById("feed");
  feed.innerHTML = "";
  const list = DATA.items.filter(it => current==="all" || it.source_type===current);
  if (!list.length){ feed.innerHTML = "<div class='empty'>暂无相关内容</div>"; return; }
  list.forEach((it, i) => {
    const a = document.createElement("a");
    a.className = "card";
    a.href = it.url; a.target = "_blank"; a.rel = "noopener";
    a.style.animationDelay = (i*40) + "ms";

    const top = document.createElement("div"); top.className = "card-top";
    const badge = document.createElement("span");
    badge.className = "badge " + it.source_type;
    const bdot = document.createElement("span"); bdot.className = "bdot";
    badge.appendChild(bdot);
    badge.appendChild(document.createTextNode(it.source || TYPE_LABEL[it.source_type] || "资讯"));
    const time = document.createElement("span"); time.className = "time";
    time.textContent = relTime(it.published);
    top.appendChild(badge); top.appendChild(time);

    const h = document.createElement("h2"); h.textContent = it.title;

    const p = document.createElement("p");
    p.textContent = it.summary || "点击查看原文详情 →";

    const foot = document.createElement("div"); foot.className = "card-foot";
    if (it.source_type === "news"){
      const m = document.createElement("span");
      m.textContent = `▲ ${it.points||0}  ·  💬 ${it.comments||0}`;
      foot.appendChild(m);
    } else if (it.author){
      const au = document.createElement("span"); au.textContent = it.author;
      foot.appendChild(au);
    }
    const go = document.createElement("span"); go.className = "go";
    go.textContent = "阅读 →";
    foot.appendChild(go);

    a.appendChild(top); a.appendChild(h); a.appendChild(p); a.appendChild(foot);
    feed.appendChild(a);
  });
}

// 分段控制器
const seg = document.getElementById("seg");
const pill = document.getElementById("pill");
const btns = [...seg.querySelectorAll("button")];
function movePill(){
  const i = btns.findIndex(b => b.classList.contains("active"));
  pill.style.transform = `translateX(calc(${i} * 100%))`;
  pill.style.width = `calc((100% - 8px) / ${btns.length})`;
}
btns.forEach(b => b.addEventListener("click", () => {
  btns.forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  current = b.dataset.f;
  movePill(); render();
}));
window.addEventListener("resize", movePill);
movePill();
render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
