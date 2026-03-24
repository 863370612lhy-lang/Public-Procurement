#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招标信息采集器 v3
- 更精准的关键词（尤其烟草类）
- 每条数据强制显示时间和地区
- 生成的网页带时间筛选按钮（24h/3天/7天/30天/全部）
"""

import json, time, random, hashlib, os, re
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://www.ccgp.gov.cn/",
}

DAYS_BACK = int(os.environ.get("DAYS_BACK", "90"))

CATEGORIES = [
    {
        "id": "smoke",
        "icon": "🚬",
        "name": "烟草吸烟室 / 吸烟环境",
        "keywords": [
            "文明吸烟",
            "吸烟室",
            "吸烟环境",
            "吸烟亭",
            "烟草 吸烟",
            "吸烟区建设",
            "吸烟设施",
            "控烟设施",
            "吸烟间",
        ]
    },
    {
        "id": "tobacco",
        "icon": "🏢",
        "name": "烟草公司相关采购",
        "keywords": [
            "烟草公司",
            "烟草局",
            "中烟",
            "烟草专卖",
            "烟草集团",
            "省烟草",
            "市烟草",
            "烟草有限公司",
            "烟草工业",
            "烟草商业",
        ]
    },
    {
        "id": "box",
        "icon": "📦",
        "name": "集装箱厢房 / 活动房",
        "keywords": [
            "集装箱房",
            "集装箱厢房",
            "住人集装箱",
            "集装箱活动房",
            "集装箱板房",
            "集装箱宿舍",
            "活动板房",
            "移动板房",
            "箱式房",
        ]
    },
    {
        "id": "trash",
        "icon": "🗑️",
        "name": "垃圾房 / 垃圾亭",
        "keywords": [
            "垃圾房",
            "垃圾亭",
            "垃圾收集房",
            "分类垃圾",
            "垃圾中转",
            "垃圾收集亭",
            "垃圾分类亭",
            "果皮箱",
            "垃圾桶采购",
        ]
    },
    {
        "id": "toilet",
        "icon": "🚻",
        "name": "移动公厕 / 装配式公厕",
        "keywords": [
            "移动公厕",
            "移动厕所",
            "装配式公厕",
            "智慧公厕",
            "环保公厕",
            "一体化公厕",
            "移动卫生间",
            "生态公厕",
            "公厕建设",
        ]
    }
]


def safe_get(url, **kwargs):
    try:
        kwargs.setdefault("timeout", 15)
        kwargs.setdefault("headers", HEADERS)
        r = requests.get(url, **kwargs)
        r.encoding = "utf-8"
        return r
    except Exception as e:
        print(f"    [请求失败] {str(e)[:60]}")
        return None


def sleep_a_bit():
    time.sleep(random.uniform(2.0, 4.0))


def normalize_date(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.strip()
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return raw[:10] if len(raw) >= 10 else raw


def search_ccgp(keyword: str, days: int) -> list:
    now = datetime.now()
    start = now - timedelta(days=days)
    results = []

    for page in range(1, 4):
        params = {
            "searchtype": "1", "bidSort": "0", "buyerName": "", "projectId": "",
            "pinMu": "0", "bidType": "0", "dbselect": "bidx",
            "kw": keyword,
            "start_time": start.strftime("%Y:%m:%d"),
            "end_time": now.strftime("%Y:%m:%d"),
            "timeType": "6", "displayZone": "", "zoneId": "", "pppStatus": "0",
            "agentName": "", "page_index": str(page),
        }
        url = "http://search.ccgp.gov.cn/bxsearch?" + urlencode(params)
        r = safe_get(url)
        if not r:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        lis = soup.select("ul.vT-srch-result-list-bid li")
        if not lis:
            break

        for li in lis:
            a = li.select_one("a")
            if not a:
                continue
            title = a.get_text(" ", strip=True).replace("\n", " ")
            if not title or len(title) < 5:
                continue
            href = a.get("href", "")
            if href and not href.startswith("http"):
                href = "http://www.ccgp.gov.cn" + href

            buyer = zone = pub_date = ""
            for span in li.select("span"):
                cls = " ".join(span.get("class", []))
                txt = span.get_text(strip=True)
                if "Buyer" in cls or "buyer" in cls:
                    buyer = txt
                elif any(w in cls for w in ["Area","area","Zone","zone"]):
                    zone = txt
                elif "date" in cls.lower() or "time" in cls.lower() or "Date" in cls:
                    pub_date = normalize_date(txt)

            if not pub_date:
                m = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', li.get_text())
                if m:
                    pub_date = normalize_date(m.group(1))

            results.append({
                "title": title, "buyer": buyer, "zone": zone,
                "budget": "未披露", "pub_date": pub_date,
                "source": "中国政府采购网", "url": href,
            })
        sleep_a_bit()

    print(f"  [ccgp] '{keyword}' → {len(results)} 条")
    return results


def search_zcygov(keyword: str) -> list:
    results = []
    try:
        url = "https://www.zcygov.cn/search/search-purchase-announcement"
        for page in range(1, 3):
            r = safe_get(url, params={"keyword": keyword, "currentPage": page, "pageSize": 15})
            if not r:
                break
            data = r.json()
            recs = (data.get("data") or {}).get("records") or []
            if not recs:
                break
            for item in recs:
                title = item.get("title", "")
                if not title:
                    continue
                results.append({
                    "title": title,
                    "buyer": item.get("buyerName", ""),
                    "zone": item.get("areaName", ""),
                    "budget": item.get("budget", "未披露") or "未披露",
                    "pub_date": normalize_date(str(item.get("publishTime", ""))[:10]),
                    "source": "采购云平台",
                    "url": item.get("url") or item.get("detailUrl", ""),
                })
            sleep_a_bit()
    except Exception as e:
        print(f"  [zcygov失败] {keyword}: {e}")
    print(f"  [zcygov] '{keyword}' → {len(results)} 条")
    return results


def search_bidcenter(keyword: str) -> list:
    results = []
    try:
        for page in range(1, 3):
            url = f"https://www.bidcenter.com.cn/search/?keyword={quote(keyword)}&page={page}"
            r = safe_get(url)
            if not r:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            found = []
            for sel in ["div.search-list-item", "div.result-item", "li.bid-item"]:
                found = soup.select(sel)
                if found:
                    break
            if not found:
                for a in soup.select("a[href*='/news-']"):
                    title = a.get_text(strip=True)
                    if len(title) > 8 and any(w in title for w in ["招标","采购","公告","竞争","磋商"]):
                        href = a.get("href","")
                        if not href.startswith("http"):
                            href = "https://www.bidcenter.com.cn" + href
                        results.append({
                            "title": title, "buyer": "", "zone": "",
                            "budget": "未披露", "pub_date": "",
                            "source": "必联网", "url": href,
                        })
                break
            for el in found[:10]:
                a = el.select_one("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                if not title or len(title) < 6:
                    continue
                if not any(w in title for w in ["招标","采购","公告","竞争","磋商","询价"]):
                    continue
                href = a.get("href","")
                if not href.startswith("http"):
                    href = "https://www.bidcenter.com.cn" + href
                date_el = el.select_one(".time,.date,span[class*='date'],span[class*='time']")
                zone_el = el.select_one(".area,.zone,span[class*='area']")
                buyer_el = el.select_one(".buyer,.company,span[class*='buyer']")
                pub_date = normalize_date(date_el.get_text(strip=True)) if date_el else ""
                if not pub_date:
                    m = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', el.get_text())
                    if m:
                        pub_date = normalize_date(m.group(1))
                results.append({
                    "title": title,
                    "buyer": buyer_el.get_text(strip=True) if buyer_el else "",
                    "zone": zone_el.get_text(strip=True) if zone_el else "",
                    "budget": "未披露", "pub_date": pub_date,
                    "source": "必联网", "url": href,
                })
            sleep_a_bit()
    except Exception as e:
        print(f"  [bidcenter失败] {keyword}: {e}")
    print(f"  [bidcenter] '{keyword}' → {len(results)} 条")
    return results


def search_bids_gov(keyword: str) -> list:
    results = []
    try:
        url = "https://search.bids.gov.cn/query/search"
        r = safe_get(url, params={"keyword": keyword, "pageNo": 1, "pageSize": 15, "sort": "time"})
        if not r:
            return results
        try:
            data = r.json()
            items = (data.get("data") or {}).get("list") or []
            for item in items:
                title = item.get("title") or item.get("projectName","")
                if not title:
                    continue
                results.append({
                    "title": title,
                    "buyer": item.get("tenderee") or item.get("buyerName",""),
                    "zone": item.get("area") or item.get("province",""),
                    "budget": "未披露",
                    "pub_date": normalize_date(str(item.get("publishTime",""))[:10]),
                    "source": "招标投标公共服务平台",
                    "url": item.get("url") or item.get("detailUrl",""),
                })
        except Exception:
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href]")[:15]:
                title = a.get_text(strip=True)
                if len(title) > 8 and any(w in title for w in ["招标","采购","公告"]):
                    results.append({
                        "title": title, "buyer": "", "zone": "",
                        "budget": "未披露", "pub_date": "",
                        "source": "招标投标公共服务平台",
                        "url": a.get("href",""),
                    })
        sleep_a_bit()
    except Exception as e:
        print(f"  [bids.gov失败] {keyword}: {e}")
    print(f"  [bids.gov] '{keyword}' → {len(results)} 条")
    return results


def dedup(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        key = hashlib.md5(item["title"][:25].encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            out.append(item)
    out.sort(key=lambda x: x.get("pub_date","") or "0000-00-00", reverse=True)
    return out


def collect_all() -> dict:
    results = {}
    for cat in CATEGORIES:
        print(f"\n{'='*45}\n  {cat['icon']} {cat['name']}\n{'='*45}")
        all_items = []
        for kw in cat["keywords"]:
            print(f"\n  关键词：「{kw}」")
            all_items += search_ccgp(kw, DAYS_BACK)
            all_items += search_zcygov(kw)
            all_items += search_bidcenter(kw)
            all_items += search_bids_gov(kw)
        unique = dedup(all_items)
        print(f"\n  OK 去重后共 {len(unique)} 条")
        results[cat["id"]] = {"cat": cat, "items": unique[:50]}
    return results


def generate_html(results: dict) -> str:
    run_date = datetime.now().strftime("%Y年%m月%d日")
    run_time = datetime.now().strftime("%H:%M")
    total = sum(len(v["items"]) for v in results.values())

    cats_html = ""
    for cat_id, data in results.items():
        cat = data["cat"]
        items = data["items"]
        if not items:
            rows = '<div class="empty"><p>本次采集暂无该类别信息，明天自动更新</p></div>'
        else:
            rows = ""
            for item in items:
                url = item.get("url","")
                has_url = url.startswith("http")
                pub_date = item.get("pub_date","") or ""
                zone = item.get("zone","") or ""
                buyer = item.get("buyer","") or ""
                budget = item.get("budget","") or ""
                source = item.get("source","") or "网络来源"
                title_html = (f'<a href="{url}" target="_blank">{item["title"]}</a>' if has_url else item["title"])
                date_badge = (f'<span class="date-badge">📅 {pub_date}</span>' if pub_date else '<span class="date-badge no-date">📅 日期待确认</span>')
                zone_badge = (f'<span class="zone-badge">📍 {zone}</span>' if zone else '')
                metas = []
                if buyer:
                    metas.append(f'<span class="meta"><span class="dot"></span>{buyer}</span>')
                if budget and budget != "未披露":
                    metas.append(f'<span class="meta"><span class="dot"></span>💰 {budget}</span>')
                metas.append(f'<span class="meta src-tag">{source}</span>')
                link_btn = (f'<a href="{url}" target="_blank" class="link-btn">查看原文 →</a>' if has_url else '<span class="link-btn dim">暂无链接</span>')
                rows += f'<div class="item" data-date="{pub_date}" data-cat="{cat_id}"><div class="ib"><div class="it">{title_html}</div><div class="dzr">{date_badge}{zone_badge}</div><div class="im">{"".join(metas)}</div></div><div class="ia">{link_btn}</div></div>'

        cats_html += f'<div class="cb" data-cat="{cat_id}"><div class="ch"><span class="ci">{cat["icon"]}</span><span class="ct">{cat["name"]}</span><span class="cc" id="count-{cat_id}">{len(items)} 条</span></div><div class="cl" id="list-{cat_id}">{rows}</div></div>'

    tabs = '<button class="tab active" onclick="fc(\'all\',this)">全部</button>'
    for cat_id, data in results.items():
        cat = data["cat"]
        n = len(data["items"])
        short = cat["name"].split("/")[0].strip()
        tabs += f'<button class="tab" onclick="fc(\'{cat_id}\',this)">{cat["icon"]} {short}（{n}）</button>'

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>招标信息日报 · {run_date}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1C1C1E;--mu:#8E8E93;--go:#B8860B;--gl:#D4A017;--gp:#FDF8EC;--gb:#E8D5A0;--sf:#FAFAF8;--wh:#fff;--bd:#E5E2D9;--tg:#F0EDE4}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{font-family:'Noto Sans SC',sans-serif;background:var(--sf);color:var(--ink)}}
.tb{{background:var(--ink);padding:0 40px;display:flex;align-items:center;justify-content:space-between;height:52px;position:sticky;top:0;z-index:100}}
.lo{{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:600;color:#fff;display:flex;align-items:center;gap:10px}}
.lo::before{{content:'';width:5px;height:18px;background:var(--gl);display:block}}
.td{{font-size:12px;color:rgba(255,255,255,.45)}}
.he{{background:var(--ink);padding:36px 40px 52px;position:relative}}
.he::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--go),transparent)}}
.hi{{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:40px;align-items:center}}
.ht{{font-family:'Noto Serif SC',serif;font-size:clamp(20px,2.8vw,32px);font-weight:700;color:#fff;line-height:1.3;margin-bottom:8px}}
.ht span{{color:var(--gl)}}
.hs{{font-size:13px;color:rgba(255,255,255,.4);line-height:1.8}}
.sr{{display:flex;border:1px solid rgba(255,255,255,.1)}}
.sb{{padding:14px 22px;text-align:center;border-right:1px solid rgba(255,255,255,.08)}}
.sb:last-child{{border-right:none}}
.sn{{font-family:'Noto Serif SC',serif;font-size:24px;font-weight:700;color:var(--gl);display:block}}
.sl{{font-size:10px;color:rgba(255,255,255,.3);margin-top:2px;letter-spacing:1px}}
.ctrl{{max-width:1080px;margin:0 auto;padding:18px 40px 0}}
.ctrl-inner{{background:var(--wh);border:1px solid var(--bd);padding:12px 18px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}}
.ctrl-group{{display:flex;align-items:center;gap:6px;flex-wrap:wrap}}
.ctrl-label{{font-size:12px;color:var(--mu);white-space:nowrap;font-weight:500}}
.time-btn{{padding:4px 12px;font-size:12px;border:1px solid var(--bd);background:var(--sf);color:var(--mu);cursor:pointer;transition:all .15s}}
.time-btn.active{{background:var(--ink);color:var(--gl);border-color:var(--ink)}}
.time-btn:hover:not(.active){{border-color:var(--go);color:var(--go)}}
.cdiv{{width:1px;height:22px;background:var(--bd);flex-shrink:0}}
.zone-input{{border:1px solid var(--bd);background:var(--sf);padding:4px 10px;font-size:12px;font-family:'Noto Sans SC',sans-serif;color:var(--ink);outline:none;width:110px}}
.zone-input:focus{{border-color:var(--go)}}
.btn-s{{padding:5px 14px;background:var(--go);color:#fff;border:none;font-family:'Noto Sans SC',sans-serif;font-size:12px;cursor:pointer}}
.btn-s:hover{{background:var(--gl)}}
.btn-r{{padding:5px 10px;background:transparent;color:var(--mu);border:1px solid var(--bd);font-family:'Noto Sans SC',sans-serif;font-size:12px;cursor:pointer}}
.btn-r:hover{{border-color:var(--go);color:var(--go)}}
.rc{{font-size:12px;color:var(--mu);margin-left:auto;white-space:nowrap}}
.rc strong{{color:var(--ink)}}
.mn{{max-width:1080px;margin:0 auto;padding:18px 40px 60px}}
.smb{{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--bd);margin-bottom:22px;flex-wrap:wrap;gap:8px}}
.sml{{font-size:13px;color:var(--mu)}} .sml strong{{color:var(--ink);font-weight:500}}
.ts{{display:flex;gap:4px;flex-wrap:wrap}}
.tab{{padding:4px 12px;font-size:12px;border:1px solid var(--bd);background:var(--wh);color:var(--mu);cursor:pointer;transition:all .15s}}
.tab.active{{background:var(--ink);color:var(--gl);border-color:var(--ink)}}
.tab:hover:not(.active){{border-color:var(--go);color:var(--go)}}
.cb{{margin-bottom:30px}}
.ch{{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:2px solid var(--ink)}}
.ci{{font-size:15px}}.ct{{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600}}
.cc{{margin-left:auto;font-size:12px;padding:2px 10px;background:var(--gp);color:var(--go);border:1px solid var(--gb)}}
.cl{{border:1px solid var(--bd);border-top:none}}
.item{{display:grid;grid-template-columns:1fr auto;gap:12px;padding:14px 18px;border-bottom:1px solid var(--bd);background:var(--wh);transition:background .15s}}
.item:last-child{{border-bottom:none}}.item:hover{{background:var(--gp)}}.item.hidden{{display:none!important}}
.it{{font-size:14px;font-weight:500;line-height:1.6;margin-bottom:5px}}
.it a{{color:var(--ink);text-decoration:none}}.it a:hover{{color:var(--go)}}
.dzr{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:5px;align-items:center}}
.date-badge{{display:inline-flex;align-items:center;font-size:12px;font-weight:500;color:#0C447C;background:#E6F1FB;padding:2px 9px;border:1px solid #B5D4F4}}
.date-badge.no-date{{color:var(--mu);background:var(--tg);border-color:var(--bd)}}
.zone-badge{{display:inline-flex;align-items:center;font-size:12px;font-weight:500;color:#0F6E56;background:#E1F5EE;padding:2px 9px;border:1px solid #9FE1CB}}
.im{{display:flex;gap:10px;flex-wrap:wrap}}
.meta{{font-size:12px;color:var(--mu);display:flex;align-items:center;gap:3px}}
.dot{{width:3px;height:3px;background:var(--go);border-radius:50%;flex-shrink:0}}
.src-tag{{background:var(--tg);padding:1px 5px;font-size:11px}}
.ia{{display:flex;align-items:center;flex-shrink:0}}
.link-btn{{font-size:12px;color:var(--go);text-decoration:none;border:1px solid var(--gb);padding:4px 12px;white-space:nowrap;transition:all .15s}}
.link-btn:hover{{background:var(--go);color:#fff}}.link-btn.dim{{opacity:.3;cursor:default}}
.empty{{text-align:center;padding:32px;border:1px dashed var(--bd);border-top:none;background:var(--wh)}}
.empty p{{font-size:13px;color:var(--mu)}}
.no-res{{text-align:center;padding:40px;font-size:13px;color:var(--mu);display:none;background:var(--wh);border:1px dashed var(--bd)}}
.ft{{background:var(--ink);color:rgba(255,255,255,.3);text-align:center;padding:24px 40px;font-size:12px;line-height:2}}
.ft strong{{color:var(--gl);font-weight:400}}
.ft button{{margin-top:6px;padding:4px 14px;border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.5);background:transparent;cursor:pointer;font-size:12px}}
@media(max-width:680px){{.hi{{display:block}}.sr{{display:grid;grid-template-columns:1fr 1fr;margin-top:14px}}.mn,.tb,.he,.ctrl{{padding-left:14px;padding-right:14px}}.item{{grid-template-columns:1fr}}.ctrl-inner{{flex-direction:column;align-items:flex-start}}}}
</style>
</head>
<body>
<div class="tb"><div class="lo">招标信息智能日报系统</div><div class="td">{run_date} {run_time} 自动更新</div></div>
<div class="he"><div class="hi">
  <div>
    <div class="ht">每日<span>招标信息</span>日报<br>服务端采集 · 数据真实可靠</div>
    <div class="hs">数据来自中国政府采购网、必联网、采购云平台等4个官方公开渠道<br>每天 12:00 自动更新 · 每条均标注发布时间和地区</div>
  </div>
  <div class="sr">
    <div class="sb"><span class="sn" id="dt">{total}</span><div class="sl">筛选后条数</div></div>
    <div class="sb"><span class="sn">4</span><div class="sl">数据来源</div></div>
    <div class="sb"><span class="sn">{DAYS_BACK}天</span><div class="sl">采集范围</div></div>
  </div>
</div></div>
<div class="ctrl"><div class="ctrl-inner">
  <div class="ctrl-group">
    <span class="ctrl-label">⏱ 时间</span>
    <button class="time-btn" onclick="ft(1,this)">24小时内</button>
    <button class="time-btn" onclick="ft(3,this)">近3天</button>
    <button class="time-btn" onclick="ft(7,this)">近7天</button>
    <button class="time-btn active" onclick="ft(30,this)">近30天</button>
    <button class="time-btn" onclick="ft(90,this)">近90天</button>
    <button class="time-btn" onclick="ft(365,this)">近一年</button>
    <button class="time-btn" onclick="ft(0,this)">全部</button>
  </div>
  <div class="cdiv"></div>
  <div class="ctrl-group">
    <span class="ctrl-label">📍 地区</span>
    <input class="zone-input" type="text" id="zi" placeholder="如：广东、上海">
    <button class="btn-s" onclick="af()">搜索</button>
    <button class="btn-r" onclick="rf()">重置</button>
  </div>
  <span class="rc">当前显示 <strong id="sc">{total}</strong> 条</span>
</div></div>
<div class="mn">
  <div class="smb">
    <div class="sml">共采集 <strong>{total}</strong> 条 &nbsp;·&nbsp; 更新：{run_date} {run_time}</div>
    <div class="ts" id="tabs">{tabs}</div>
  </div>
  <div id="res">{cats_html}</div>
  <div class="no-res" id="nr">当前筛选条件下没有符合的招标信息，请调整时间范围或清空地区筛选</div>
</div>
<div class="ft">
  数据来源：<strong>中国政府采购网</strong>·<strong>必联网</strong>·<strong>采购云平台</strong>·<strong>招标投标公共服务平台</strong><br>
  每天北京时间12:00由GitHub Actions自动采集·数据均为公开招标公告，仅供参考<br>
  <button onclick="window.print()">打印 / 保存PDF</button>
</div>
<script>
let CC='all',CD=30,CZ='';
function fc(id,el){{CC=id;document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));if(el)el.classList.add('active');af();}}
function ft(d,el){{CD=d;document.querySelectorAll('.time-btn').forEach(b=>b.classList.remove('active'));if(el)el.classList.add('active');af();}}
function af(){{
  CZ=document.getElementById('zi').value.trim();
  const now=new Date();let shown=0;
  document.querySelectorAll('.item').forEach(item=>{{
    const cat=item.dataset.cat,ds=item.dataset.date;
    const txt=item.querySelector('.it')?item.querySelector('.it').textContent:'';
    const zb=item.querySelector('.zone-badge')?item.querySelector('.zone-badge').textContent:'';
    if(CC!=='all'&&cat!==CC){{item.classList.add('hidden');return;}}
    if(CD>0&&ds){{const diff=(now-new Date(ds))/(86400000);if(diff>CD){{item.classList.add('hidden');return;}}}}
    if(CZ&&!(txt+zb).includes(CZ)){{item.classList.add('hidden');return;}}
    item.classList.remove('hidden');shown++;
  }});
  document.getElementById('sc').textContent=shown;
  document.getElementById('dt').textContent=shown;
  document.getElementById('nr').style.display=shown===0?'block':'none';
  document.querySelectorAll('.cb').forEach(cb=>{{
    const id=cb.dataset.cat;
    const v=cb.querySelectorAll('.item:not(.hidden)').length;
    const el=document.getElementById('count-'+id);
    if(el)el.textContent=v+' 条';
    cb.style.display=(CC!=='all'&&id!==CC)?'none':'block';
  }});
}}
function rf(){{CZ='';CD=30;document.getElementById('zi').value='';document.querySelectorAll('.time-btn').forEach(b=>b.classList.toggle('active',b.textContent==='近30天'));af();}}
af();
</script>
</body>
</html>"""


def main():
    print(f"\n{'='*50}\n  招标信息采集 v3  {datetime.now().strftime('%Y-%m-%d %H:%M')}\n  采集范围：近{DAYS_BACK}天 | 4平台\n{'='*50}")
    results = collect_all()
    total = sum(len(v["items"]) for v in results.values())
    print(f"\n✅ 采集完成，共 {total} 条")
    html = generate_html(results)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)
    with open("data.json","w",encoding="utf-8") as f:
        json.dump({"run_date":datetime.now().strftime("%Y-%m-%d %H:%M"),"total":total,"categories":{k:{"name":v["cat"]["name"],"count":len(v["items"]),"items":v["items"]} for k,v in results.items()}},f,ensure_ascii=False,indent=2)
    print("✅ 文件生成完毕")

if __name__=="__main__":
    main()
