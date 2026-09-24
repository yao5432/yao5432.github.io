#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日自动生成 · iOS 风格资讯网站 (GitHub Pages 适用)
---------------------------------------------------
两大板块：
  1) AI 科技类  —— Hacker News / arXiv / 科技媒体 RSS
  2) 竞技体育类  —— ESPN 新闻 / BBC Sport RSS / Reddit 体育社区
（所有来源均无需 API Key）

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

# 竞技体育源（RSS，无需 Key；Reddit 作为补充）
SPORTS_RSS_FEEDS = [
    ("ESPN 足球", "https://www.espn.com/espn/rss/soccer/news", "soccer"),
    ("ESPN NBA", "https://www.espn.com/espn/rss/nba/news", "basketball"),
    ("ESPN NFL", "https://www.espn.com/espn/rss/nfl/news", "general"),
    ("ESPN MLB", "https://www.espn.com/espn/rss/mlb/news", "general"),
    ("ESPN 网球", "https://www.espn.com/espn/rss/tennis/news", "general"),
    ("BBC Sport", "http://feeds.bbci.co.uk/sport/rss.xml", "general"),
]
REDDIT_SPORTS = [("soccer", "soccer"), ("nba", "basketball"), ("sports", "general")]

# 军事政治源（RSS，无需 Key）
MIL_RSS_FEEDS = [
    ("BBC 国际", "http://feeds.bbci.co.uk/news/world/rss.xml", "world"),
    ("BBC 政治", "http://feeds.bbci.co.uk/news/politics/rss.xml", "politics"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "world"),
    ("Google 军事", "https://news.google.com/rss/search?q=military+OR+defense+OR+geopolitics+OR+election&hl=en-US&gl=US&ceid=US:en", "military"),
]
REDDIT_MIL = [("worldnews", "world"), ("geopolitics", "politics"), ("military", "military")]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}


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
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


# ----------------------------- AI 科技类数据源 -----------------------------
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
                pts = h.get("points") or 0
                cms = h.get("num_comments") or 0
                items[oid] = {
                    "title": clean(title),
                    "summary": f"Hacker News 社区热议话题，当前热度 ▲{pts} · 💬{cms}。",
                    "full": (f"社区热门讨论：在 Hacker News 上获得 {pts} 赞、{cms} 条评论，"
                             f"属于近期 AI 领域关注度较高的话题之一。\n\n"
                             f"原标题：{clean(title)}"),
                    "url": link,
                    "source": "Hacker News", "sub": "news", "category": "ai",
                    "points": pts, "comments": cms,
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
                "full": summary,
                "url": link,
                "source": "arXiv", "sub": "paper", "category": "ai",
                "points": 0, "comments": 0,
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
                    "full": clean(e.get("summary") or e.get("description") or ""),
                    "url": e.get("link", ""),
                    "source": name, "sub": "media", "category": "ai",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS] {name} 抓取失败: {ex}", file=sys.stderr)
    return out


# ----------------------------- 竞技体育类数据源 -----------------------------
def fetch_sports_rss():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过体育媒体源", file=sys.stderr)
        return []
    out = []
    for name, url, stype in SPORTS_RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:5]:
                title = clean(e.get("title", ""))
                if not title:
                    continue
                desc = clean(e.get("summary") or e.get("description") or "")
                out.append({
                    "title": title,
                    "summary": desc,
                    "full": desc or "（体育资讯，暂无详细正文。）",
                    "url": e.get("link", ""),
                    "source": name, "sub": stype, "category": "sports",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS {name}] 抓取失败: {ex}", file=sys.stderr)
    return out


def fetch_reddit_sports():
    out = []
    for sub_name, stype in REDDIT_SPORTS:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/.json?limit=6"
            data = fetch_json(url)
            for c in (data.get("data", {}) or {}).get("children", []):
                d = c.get("data", {})
                title = clean(d.get("title"))
                if not title:
                    continue
                selftext = clean(d.get("selftext"))[:600]
                cu = d.get("created_utc") or 0
                pub = (datetime.utcfromtimestamp(cu).isoformat() + "Z") if cu else ""
                out.append({
                    "title": title,
                    "summary": selftext,
                    "full": selftext or "（社区讨论帖，暂无正文摘要。）",
                    "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                    "source": "Reddit r/" + sub_name, "sub": stype, "category": "sports",
                    "points": d.get("score") or 0, "comments": d.get("num_comments") or 0,
                    "author": d.get("author") or "", "published": pub,
                })
        except Exception as e:
            print(f"  [Reddit r/{sub_name}] 抓取失败: {e}", file=sys.stderr)
    return out


# ----------------------------- 军事政治类数据源 -----------------------------
def fetch_military():
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 未安装 feedparser，已跳过军事政治媒体源", file=sys.stderr)
        return []
    out = []
    for name, url, stype in MIL_RSS_FEEDS:
        try:
            d = feedparser.parse(url)
            for e in d.entries[:6]:
                title = clean(e.get("title", ""))
                if not title:
                    continue
                desc = clean(e.get("summary") or e.get("description") or "")
                out.append({
                    "title": title,
                    "summary": desc,
                    "full": desc or "（时事资讯，暂无详细正文。）",
                    "url": e.get("link", ""),
                    "source": name, "sub": stype, "category": "mil",
                    "points": 0, "comments": 0, "author": "",
                    "published": e.get("published") or e.get("updated") or "",
                })
        except Exception as ex:
            print(f"  [RSS {name}] 抓取失败: {ex}", file=sys.stderr)
    return out


def fetch_reddit_mil():
    out = []
    for sub_name, stype in REDDIT_MIL:
        try:
            url = f"https://www.reddit.com/r/{sub_name}/.json?limit=6"
            data = fetch_json(url)
            for c in (data.get("data", {}) or {}).get("children", []):
                d = c.get("data", {})
                title = clean(d.get("title"))
                if not title:
                    continue
                selftext = clean(d.get("selftext"))[:600]
                cu = d.get("created_utc") or 0
                pub = (datetime.utcfromtimestamp(cu).isoformat() + "Z") if cu else ""
                out.append({
                    "title": title,
                    "summary": selftext,
                    "full": selftext or "（社区讨论帖，暂无正文摘要。）",
                    "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                    "source": "Reddit r/" + sub_name, "sub": stype, "category": "mil",
                    "points": d.get("score") or 0, "comments": d.get("num_comments") or 0,
                    "author": d.get("author") or "", "published": pub,
                })
        except Exception as e:
            print(f"  [Reddit r/{sub_name}] 抓取失败: {e}", file=sys.stderr)
    return out


# ----------------------------- 翻译（保留英文，下方中文） -----------------------------
import time

def translate_en_zh(text, retries=2):
    """调用 Google 免费翻译接口（sl=auto 自动识别，中文原文不会被破坏）。"""
    if not text or not text.strip():
        return ""
    try:
        q = urllib.parse.quote(text.strip())
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx"
               f"&sl=auto&tl=zh-CN&dt=t&q={q}")
        data = fetch_json(url)
        return "".join(seg[0] for seg in data[0] if seg[0]).strip()
    except Exception as e:
        if retries > 0:
            time.sleep(0.6)
            return translate_en_zh(text, retries - 1)
        return ""


SEP = "[[S]]"
def is_cjk(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s or ''))


def translate_item(it):
    """逐字段翻译：英文内容译为中文，中文内容原样保留（避免中英混排导致漏译）。"""
    it["title_zh"] = translate_en_zh(it.get("title", ""))
    it["summary_zh"] = (translate_en_zh(it.get("summary", ""))
                        if not is_cjk(it.get("summary", "")) else it.get("summary", ""))
    it["full_zh"] = (translate_en_zh(it.get("full", ""))
                     if not is_cjk(it.get("full", "")) else it.get("full", ""))
    return it


# ----------------------------- 离线兜底数据 -----------------------------
SAMPLE_AI = [
    {
        "title": "示例：OpenAI 发布新一代多模态推理模型",
        "summary": "社区热议话题，当前热度 ▲1280 · 💬342。",
        "full": "社区热门讨论：在 Hacker News 上获得 1280 赞、342 条评论，属于近期 AI 领域关注度较高的话题之一。\n\n原标题：OpenAI 发布新一代多模态推理模型",
        "url": "https://github.com", "source": "Hacker News", "sub": "news", "category": "ai",
        "points": 1280, "comments": 342, "author": "demo",
        "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    {
        "title": "示例：arXiv 论文 — 高效稀疏注意力机制综述",
        "summary": "A survey on efficient sparse attention for long-context large language models.",
        "full": "A survey on efficient sparse attention for long-context large language models. We systematically review recent advances in sparse attention that reduce the quadratic cost of standard transformers, enabling context lengths of hundreds of thousands of tokens while preserving model quality across downstream tasks.",
        "url": "https://arxiv.org", "source": "arXiv", "sub": "paper", "category": "ai",
        "points": 0, "comments": 0, "author": "Demo Authors",
        "published": (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
    },
    {
        "title": "示例：科技媒体报道 AI 芯片竞争格局变化",
        "summary": "行业观察：新入局者正在重塑 AI 加速器的供应格局。",
        "full": "行业观察：新入局者正在重塑 AI 加速器的供应格局。多家初创公司宣布自研推理芯片，试图在能效比上挑战传统 GPU 方案，预计将影响未来数据中心的成本结构。",
        "url": "https://example.com", "source": "The Verge AI", "sub": "media", "category": "ai",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat(),
    },
]

SAMPLE_SPORTS = [
    {
        "title": "示例：英超焦点战 — 争冠关键轮次悬念升级",
        "summary": "联赛进入尾声，多支球队积分胶着，本轮结果或将直接决定冠军归属与欧战席位。",
        "full": "联赛进入尾声，多支球队积分胶着，本轮结果或将直接决定冠军归属与欧战席位。主队近期状态回暖，客队则依赖核心前锋的终结效率。赛前数据显示双方控球率接近，比赛很可能被拖入高强度对抗的拉锯战。",
        "url": "https://www.espn.com", "source": "ESPN · 英超", "sub": "soccer", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    },
    {
        "title": "示例：NBA 季后赛 — 巨星对决引爆社交媒体",
        "summary": "一场高强度对攻让系列赛大比分被扳平，球迷讨论度创下赛季新高。",
        "full": "一场高强度对攻让系列赛大比分被扳平，球迷讨论度创下赛季新高。双方在末节多次交替领先，关键回合的防守选择成为赛后分析的重点。伤病情况与轮换深度，将成为接下来客场之旅的最大变数。",
        "url": "https://www.espn.com", "source": "ESPN · NBA", "sub": "basketball", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
    },
    {
        "title": "示例：F1 新规则季前测试引爆话题",
        "summary": "各车队在季前测试中展现全新空气动力学方案，围场内外猜测不断。",
        "full": "各车队在季前测试中展现全新空气动力学方案，围场内外猜测不断。动力单元可靠性和轮胎管理成为媒体聚焦的两条主线，而中游集团的竞争被认为将是本赛季最激烈的看点。",
        "url": "https://www.espn.com", "source": "ESPN · F1", "sub": "general", "category": "sports",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
    },
]

SAMPLE_MIL = [
    {
        "title": "示例：主要国家就地区安全局势举行多边磋商",
        "summary": "多国代表围绕地区稳定与防务合作展开闭门会谈，外界关注后续联合声明。",
        "full": "多国代表围绕地区稳定与防务合作展开闭门会谈，外界关注后续联合声明。分析认为，此次磋商将影响未来数月的外交走向与军事部署节奏。",
        "url": "https://example.com", "source": "BBC 国际", "sub": "world", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    },
    {
        "title": "示例：国会就新财年国防预算案进入辩论阶段",
        "summary": "预算分配成为两党焦点，争议集中在装备采购与海外驻军规模。",
        "full": "预算分配成为两党焦点，争议集中在装备采购与海外驻军规模。支持方强调战略竞争需要持续投入，反对方则呼吁将资金更多转向民生领域。",
        "url": "https://example.com", "source": "BBC 政治", "sub": "politics", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat(),
    },
    {
        "title": "示例：海军舰艇编队完成远洋联合训练",
        "summary": "多型主力舰参与演训，重点检验远海补给与协同指挥能力。",
        "full": "多型主力舰参与演训，重点检验远海补给与协同指挥能力。官方通报称，训练达到预期目标，提升了复杂电磁环境下的体系作战水平。",
        "url": "https://example.com", "source": "Google 军事", "sub": "military", "category": "mil",
        "points": 0, "comments": 0, "author": "",
        "published": (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat(),
    },
]


# ----------------------------- 处理 & 主流程 -----------------------------
def process(items):
    for it in items:
        it["_dt"] = parse_time(it["published"])
    items.sort(key=lambda x: x["_dt"] or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    MAX_SUM = 120
    for it in items:
        raw = (it.get("summary") or "").strip()
        it["full"] = it.get("full") or raw
        s = raw
        if len(s) > MAX_SUM:
            s = s[:MAX_SUM].rstrip() + "…"
        if not s:
            s = "热门话题精选，点击查看完整内容。"
        it["summary"] = s
    return [{k: v for k, v in it.items() if k != "_dt"} for it in items]


def main():
    OFFLINE = os.environ.get("OFFLINE")
    if OFFLINE:
        print("→ 离线模式：使用内置示例数据（跳过网络抓取与翻译）。")
        ai, sports, mil = SAMPLE_AI, SAMPLE_SPORTS, SAMPLE_MIL
    else:
        print("→ 正在抓取 AI 科技资讯 ...")
        ai = fetch_hn() + fetch_arxiv() + fetch_rss()
        if not ai:
            print("! AI 在线源不可用，使用离线兜底数据。", file=sys.stderr)
            ai = SAMPLE_AI

        print("→ 正在抓取竞技体育资讯 ...")
        sports = fetch_sports_rss() + fetch_reddit_sports()
        if not sports:
            print("! 体育在线源不可用，使用离线兜底数据。", file=sys.stderr)
            sports = SAMPLE_SPORTS

        print("→ 正在抓取军事政治资讯 ...")
        mil = fetch_military() + fetch_reddit_mil()
        if not mil:
            print("! 军事政治在线源不可用，使用离线兜底数据。", file=sys.stderr)
            mil = SAMPLE_MIL

    ai = process(ai)
    sports = process(sports)
    mil = process(mil)

    print("→ 正在生成中文翻译（保留英文原文）...")
    for it in ai + sports + mil:
        try:
            translate_item(it)
        except Exception as e:
            print(f"  [翻译跳过] {it.get('title','')[:30]}: {e}", file=sys.stderr)
        time.sleep(0.12)

    data = {
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "ai": {"count": len(ai), "items": ai},
        "sports": {"count": len(sports), "items": sports},
        "mil": {"count": len(mil), "items": mil},
    }

    safe = (json.dumps(data, ensure_ascii=False)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))
    out_html = HTML_TEMPLATE.replace("__DATA_JSON__", safe)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(out_html)
    print(f"✓ 已生成 index.html（AI 科技 {len(ai)} 条 · 竞技体育 {len(sports)} 条 · 军事政治 {len(mil)} 条）")


# ----------------------------- 页面模板 (iOS 风格) -----------------------------
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<meta name="theme-color" content="#f2f2f7" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#000000" media="(prefers-color-scheme: dark)" />
<title>遥遥资讯</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect width='100' height='100' rx='22' fill='%23ff6a00'/%3E%3Ctext x='50' y='72' font-size='60' font-family='PingFang SC,Arial' font-weight='700' fill='white' text-anchor='middle'%3E遥%3C/text%3E%3C/svg%3E" />
<style>
  :root{
    --bg:#f2f2f7; --card:#ffffff; --text:#1c1c1e; --sub:#8e8e93;
    --line:rgba(60,60,67,.12); --accent:#ff6a00; --accent-soft:rgba(255,106,0,.12);
    --news:#ff9500; --paper:#5e5ce6; --media:#34c759; --sport:#ff3b30; --mil:#30b0c7;
    --shadow:0 1px 2px rgba(0,0,0,.06),0 10px 30px rgba(0,0,0,.07);
    --radius:20px;
  }
  @media (prefers-color-scheme: dark){
    :root{
      --bg:#000; --card:#1c1c1e; --text:#f2f2f7; --sub:#98989f;
      --line:rgba(255,255,255,.12); --accent-soft:rgba(255,138,30,.18);
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
  .hero{padding:26px 0 4px;}
  .hero h1{
    margin:0;font-size:34px;font-weight:800;letter-spacing:-.5px;
    background:linear-gradient(120deg,#ff9a00,#ff6a00 55%,#ffb84d);
    -webkit-background-clip:text;background-clip:text;color:transparent;
  }
  .hero .date{margin-top:4px;color:var(--sub);font-size:14px;}
  .hero .cnt{color:var(--accent);font-weight:600;}

  /* 分段控制器 */
  .seg{
    display:flex;gap:4px;background:var(--accent-soft);
    padding:4px;border-radius:14px;margin:14px 0 0;
    position:relative;overflow:hidden;
  }
  .seg.seg-cat{margin-top:16px;}
  .seg button{
    flex:1;border:0;background:transparent;color:var(--text);
    font-size:14px;font-weight:600;padding:9px 0;border-radius:10px;
    cursor:pointer;transition:color .25s;font-family:inherit;position:relative;z-index:2;
  }
  .seg button.active{color:var(--accent);}
  .seg .pill{
    position:absolute;top:4px;bottom:4px;left:4px;width:calc((100% - 8px)/4 - 0px);
    background:var(--card);border-radius:10px;box-shadow:var(--shadow);
    transition:transform .3s cubic-bezier(.4,1.3,.5,1);z-index:1;
  }
  .seg.seg-cat{background:rgba(255,106,0,.10);}
  .seg.seg-cat .pill{background:linear-gradient(120deg,#ff9a00,#ff6a00);box-shadow:0 4px 14px rgba(255,106,0,.35);}
  .seg.seg-cat button.active{color:#fff;}

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
  .badge.sports{background:rgba(255,59,48,.15);color:var(--sport);} .badge.sports .bdot{background:var(--sport);}
  .badge.mil{background:rgba(48,176,199,.16);color:var(--mil);} .badge.mil .bdot{background:var(--mil);}
  .time{margin-left:auto;font-size:12px;color:var(--sub);}
  .card h2{margin:0 0 4px;font-size:17px;font-weight:700;line-height:1.35;letter-spacing:-.2px;}
  .zh-title{font-size:14.5px;font-weight:600;color:var(--text);opacity:.82;margin:0 0 7px;line-height:1.4;}
  .card p{margin:0;font-size:14.5px;color:var(--sub);line-height:1.5;
    display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}
  .zh{font-size:13.5px;color:var(--sub);line-height:1.55;margin-top:6px;opacity:.95;}
  .card-foot{margin-top:11px;display:flex;align-items:center;gap:14px;font-size:12.5px;color:var(--sub);}
  .card-foot .go{margin-left:auto;color:var(--accent);font-weight:600;display:inline-flex;align-items:center;gap:3px;}

  .empty{text-align:center;color:var(--sub);padding:60px 20px;font-size:15px;}

  footer{text-align:center;color:var(--sub);font-size:12.5px;margin-top:30px;line-height:1.8;}
  footer .foot-sub{display:block;margin-top:5px;opacity:.7;font-size:11.5px;letter-spacing:.3px;}

  /* 底部详情面板 (iOS sheet) */
  .sheet-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.42);
    backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);
    opacity:0;visibility:hidden;transition:opacity .3s,visibility .3s;z-index:50;}
  .sheet-backdrop.show{opacity:1;visibility:visible;}
  .sheet{position:absolute;left:0;right:0;bottom:0;background:var(--card);
    border-radius:22px 22px 0 0;padding:10px 20px calc(26px + env(safe-area-inset-bottom));
    max-height:84vh;overflow-y:auto;transform:translateY(100%);
    transition:transform .35s cubic-bezier(.3,1,.4,1);}
  .sheet-backdrop.show .sheet{transform:none;}
  .sheet-grip{width:38px;height:5px;border-radius:3px;background:var(--line);margin:4px auto 14px;}
  .sheet-close{position:absolute;top:10px;right:12px;border:0;background:transparent;
    color:var(--sub);font-size:26px;line-height:1;cursor:pointer;padding:2px 8px;}
  .sheet .badge{margin-bottom:10px;}
  .sheet h2{margin:0 0 12px;font-size:21px;font-weight:800;line-height:1.35;letter-spacing:-.3px;padding-right:30px;}
  .sheet .s-body{font-size:15.5px;color:var(--text);line-height:1.75;white-space:pre-wrap;word-break:break-word;}
  .sheet .s-foot{margin-top:18px;font-size:13px;color:var(--sub);display:flex;gap:16px;flex-wrap:wrap;}
</style>
</head>
<body>
  <div class="nav">
    <div class="nav-in">
      <div class="nav-title">遥遥资讯</div>
      <div class="nav-up"><span class="dot"></span><span id="upd">更新中…</span></div>
    </div>
  </div>

  <div class="wrap">
    <div class="hero">
      <h1>遥遥资讯</h1>
      <div class="date" id="herodate">—</div>
    </div>

    <!-- 一级板块切换 -->
    <div class="seg seg-cat" id="segCat">
      <span class="pill" id="pillCat"></span>
      <button data-cat="ai" class="active">AI 科技</button>
      <button data-cat="sports">竞技体育</button>
      <button data-cat="mil">军事政治</button>
    </div>

    <!-- 二级筛选（按板块动态生成） -->
    <div class="seg" id="segSub"></div>

    <div id="feed"></div>

    <footer>
      由遥遥科技团队运营<br/>
      <span class="foot-sub">于信息洪流中，为你留住值得凝视的微光 · 每天一分钟，与世界同步思考</span>
    </footer>
  </div>

  <div class="sheet-backdrop" id="sheetBackdrop">
    <div class="sheet" id="sheetCard">
      <div class="sheet-grip"></div>
      <button class="sheet-close" id="sheetClose" aria-label="关闭">×</button>
      <div id="sheetBody"></div>
    </div>
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

// 板块配置：一级板块 -> 二级筛选标签
const CATS = {
  ai: {
    label: "AI 科技",
    tabs: [
      {f:"all", label:"全部"}, {f:"news", label:"资讯"},
      {f:"paper", label:"论文"}, {f:"media", label:"媒体"}
    ]
  },
  sports: {
    label: "竞技体育",
    tabs: [
      {f:"all", label:"全部"}, {f:"soccer", label:"足球"},
      {f:"basketball", label:"篮球"}, {f:"general", label:"综合"}
    ]
  },
  mil: {
    label: "军事政治",
    tabs: [
      {f:"all", label:"全部"}, {f:"world", label:"国际"},
      {f:"politics", label:"政治"}, {f:"military", label:"军事"}
    ]
  }
};
let cat = "ai";
let sub = "all";

// 导航更新时间
(() => {
  const ga = new Date(DATA.generated_at);
  document.getElementById("upd").textContent =
    "更新于 " + String(ga.getHours()).padStart(2,"0") + ":" + String(ga.getMinutes()).padStart(2,"0");
})();

function updateHero(){
  const c = (DATA[cat] && DATA[cat].count) || 0;
  document.getElementById("herodate").innerHTML =
    fmtDate(new Date()) + " · " + CATS[cat].label + " 收录 <span class='cnt'>" + c + "</span> 条";
}

// 渲染卡片
function render(){
  const feed = document.getElementById("feed");
  feed.innerHTML = "";
  const items = ((DATA[cat] && DATA[cat].items) || []).filter(it => sub==="all" || it.sub===sub);
  if (!items.length){ feed.innerHTML = "<div class='empty'>暂无相关内容</div>"; return; }
  items.forEach((it, i) => {
    const a = document.createElement("div");
    a.className = "card";
    a.style.animationDelay = (i*40) + "ms";

    const top = document.createElement("div"); top.className = "card-top";
    const badge = document.createElement("span");
    badge.className = "badge " + (it.category==="sports" ? "sports" : it.category==="mil" ? "mil" : it.sub);
    const bdot = document.createElement("span"); bdot.className = "bdot";
    badge.appendChild(bdot);
    badge.appendChild(document.createTextNode(it.source || (it.category==="sports"?"体育":it.category==="mil"?"军事政治":"资讯")));
    const time = document.createElement("span"); time.className = "time";
    time.textContent = relTime(it.published);
    top.appendChild(badge); top.appendChild(time);

    const h = document.createElement("h2"); h.textContent = it.title;
    const zhT = document.createElement("div"); zhT.className = "zh-title";
    zhT.textContent = it.title_zh || "";

    const p = document.createElement("p");
    p.textContent = it.summary || "热门话题精选，点击查看完整内容。";
    const zh = document.createElement("div"); zh.className = "zh";
    zh.textContent = it.summary_zh || "";

    const foot = document.createElement("div"); foot.className = "card-foot";
    if ((it.points||0) || (it.comments||0)){
      const m = document.createElement("span");
      m.textContent = `▲ ${it.points||0}  ·  💬 ${it.comments||0}`;
      foot.appendChild(m);
    } else if (it.author){
      const au = document.createElement("span"); au.textContent = it.author;
      foot.appendChild(au);
    }
    a.appendChild(top); a.appendChild(h);
    if (it.title_zh) a.appendChild(zhT);
    a.appendChild(p);
    if (it.summary_zh) a.appendChild(zh);
    a.appendChild(foot);
    a.addEventListener("click", () => openSheet(it));
    feed.appendChild(a);
  });
}

// 详情面板（点击卡片展开，不跳转外链）
const sheetBackdrop = document.getElementById("sheetBackdrop");
function openSheet(it){
  const body = document.getElementById("sheetBody");
  body.innerHTML = "";
  const badge = document.createElement("span");
  badge.className = "badge " + (it.category==="sports" ? "sports" : it.category==="mil" ? "mil" : it.sub);
  const bd = document.createElement("span"); bd.className = "bdot";
  badge.appendChild(bd);
  badge.appendChild(document.createTextNode(it.source || (it.category==="sports"?"体育":it.category==="mil"?"军事政治":"资讯")));
  const h = document.createElement("h2"); h.textContent = it.title;
  const zhT = document.createElement("div"); zhT.className = "zh-title";
  zhT.textContent = it.title_zh || "";
  const p = document.createElement("p"); p.className = "s-body";
  p.textContent = it.full || it.summary || "热门话题精选，点击查看完整内容。";
  const zh = document.createElement("div"); zh.className = "zh s-body";
  zh.textContent = (it.full_zh || it.summary_zh || "");
  body.appendChild(badge);
  body.appendChild(h);
  if (it.title_zh) body.appendChild(zhT);
  body.appendChild(p);
  if (it.full_zh || it.summary_zh) body.appendChild(zh);
  const foot = document.createElement("div"); foot.className = "s-foot";
  if ((it.points||0) || (it.comments||0)){
    const m = document.createElement("span");
    m.textContent = "▲ " + (it.points||0) + "  ·  💬 " + (it.comments||0);
    foot.appendChild(m);
  }
  if (it.author){ const au = document.createElement("span"); au.textContent = it.author; foot.appendChild(au); }
  const t = document.createElement("span"); t.textContent = relTime(it.published) || ""; foot.appendChild(t);
  body.appendChild(foot);
  sheetBackdrop.classList.add("show");
  document.body.style.overflow = "hidden";
}
function closeSheet(){
  sheetBackdrop.classList.remove("show");
  document.body.style.overflow = "";
}
document.getElementById("sheetClose").addEventListener("click", closeSheet);
sheetBackdrop.addEventListener("click", e => { if (e.target === sheetBackdrop) closeSheet(); });
document.addEventListener("keydown", e => { if (e.key === "Escape") closeSheet(); });

// 二级筛选（按当前板块重建）
function buildSub(){
  const seg = document.getElementById("segSub");
  seg.innerHTML = '<span class="pill" id="pillSub"></span>';
  CATS[cat].tabs.forEach((t, i) => {
    const btn = document.createElement("button");
    btn.textContent = t.label; btn.dataset.f = t.f;
    if (i === 0) btn.classList.add("active");
    seg.appendChild(btn);
  });
  const pill = seg.querySelector("#pillSub");
  const btns = [...seg.querySelectorAll("button")];
  function move(){
    const i = btns.findIndex(b => b.classList.contains("active"));
    pill.style.transform = `translateX(calc(${i} * 100%))`;
    pill.style.width = `calc((100% - 8px) / ${btns.length})`;
  }
  btns.forEach(b => b.addEventListener("click", () => {
    btns.forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    sub = b.dataset.f; move(); render();
  }));
  window.addEventListener("resize", move);
  move();
}

// 一级板块切换
const segCat = document.getElementById("segCat");
const pillCat = document.getElementById("pillCat");
const catBtns = [...segCat.querySelectorAll("button")];
function moveCat(){
  const i = catBtns.findIndex(b => b.classList.contains("active"));
  pillCat.style.transform = `translateX(calc(${i} * 100%))`;
  pillCat.style.width = `calc((100% - 8px) / ${catBtns.length})`;
}
catBtns.forEach(b => b.addEventListener("click", () => {
  catBtns.forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  cat = b.dataset.cat; sub = "all";
  moveCat(); buildSub(); updateHero(); render();
}));

moveCat();
buildSub();
updateHero();
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 任何意外错误都不再中断：打印错误，保证上一次生成的页面仍在。
        print(f"! 生成过程中出现异常（已尽量保留现有页面）: {e}", file=sys.stderr)
