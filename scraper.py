#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招标信息采集器 - 服务端运行，无 CORS 限制
数据来源：中国政府采购网（ccgp.gov.cn）官方公开接口
"""

import json
import time
import random
import hashlib
import os
import re
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

# 搜索类别与关键词
CATEGORIES = [
    {
        "id": "smoke",
        "icon": "🚬",
        "name": "烟草吸烟室 / 吸烟环境",
        "keywords": ["文明吸烟环境", "烟草吸烟室", "吸烟亭 烟草", "室内吸烟室", "烟草公司 吸烟"]
    },
    {
        "id": "tobacco",
        "icon": "🏢",
        "name": "烟草公司相关采购",
        "keywords": ["烟草公司采购", "中烟公司招标", "烟草局采购"]
    },
    {
        "id": "box",
        "icon": "📦",
        "name": "集装箱厢房 / 活动房",
        "keywords": ["集装箱厢房", "住人集装箱", "集装箱活动房", "集装箱板房"]
    },
    {
        "id": "trash",
        "icon": "🗑️",
        "name": "垃圾房 / 垃圾亭",
        "keywords": ["垃圾房采购", "分类垃圾房", "垃圾亭采购", "垃圾收集房"]
    },
    {
        "id": "toilet",
        "icon": "🚻",
        "name": "移动公厕 / 装配式公厕",
        "keywords": ["移动公厕", "装配式公厕", "移动厕所采购", "智慧公厕"]
    }
]

DAYS_BACK = int(os.environ.get("DAYS_BACK", "30"))


def search_ccgp(keyword: str, days: int = 30) -> list:
    """搜索中国政府采购网 - 官方公开接口"""
    now = datetime.now()
    start = now - timedelta(days=days)
    
    params = {
        "searchtype": "1",
        "bidSort": "0",
        "buyerName": "",
        "projectId": "",
        "pinMu": "0",
        "bidType": "0",
        "dbselect": "bidx",
        "kw": keyword,
        "start_time": start.strftime("%Y:%m:%d"),
        "end_time": now.strftime("%Y:%m:%d"),
        "timeType": "6",
        "displayZone": "",
        "zoneId": "",
        "pppStatus": "0",
        "agentName": "",
        "page_index": "1",
    }
    
    url = "http://search.ccgp.gov.cn/bxsearch?" + urlencode(params, encoding="utf-8")
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [ccgp失败] {keyword}: {e}")
        return []

    results = []
    # 主选择器
    for li in soup.select("ul.vT-srch-result-list-bid li"):
        a = li.select_one("a")
        if not a:
            continue
        title = a.get_text(strip=True).replace("\n", " ").replace("\r", "")
        if not title or len(title) < 5:
            continue
        url_link = a.get("href", "")
        if url_link and not url_link.startswith("http"):
            url_link = "http://www.ccgp.gov.cn" + url_link

        buyer = ""
        zone = ""
        pub_date = ""
        for span in li.select("span"):
            cls = " ".join(span.get("class", []))
            txt = span.get_text(strip=True)
            if "Buyer" in cls or "buyer" in cls:
                buyer = txt
            elif "Area" in cls or "area" in cls or "Zone" in cls:
                zone = txt
            elif "date" in cls.lower() or "time" in cls.lower():
                pub_date = txt

        results.append({
            "title": title,
            "buyer": buyer,
            "zone": zone,
            "budget": "未披露",
            "pub_date": pub_date,
            "source": "中国政府采购网",
            "url": url_link,
        })
    
    print(f"  [ccgp] '{keyword}' → {len(results)} 条")
    time.sleep(random.uniform(1.5, 3.0))
    return results


def search_zcygov(keyword: str, days: int = 30) -> list:
    """搜索中央采购云平台"""
    try:
        url = "https://www.zcygov.cn/search/search-purchase-announcement"
        params = {"keyword": keyword, "currentPage": 1, "pageSize": 10}
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        data = resp.json()
        items_raw = (data.get("data") or {}).get("records") or []
        results = []
        for item in items_raw:
            title = item.get("title", "")
            if not title:
                continue
            pub_date = str(item.get("publishTime", ""))[:10]
            results.append({
                "title": title,
                "buyer": item.get("buyerName", ""),
                "zone": item.get("areaName", ""),
                "budget": "未披露",
                "pub_date": pub_date,
                "source": "采购云平台",
                "url": item.get("url") or item.get("detailUrl", ""),
            })
        print(f"  [zcygov] '{keyword}' → {len(results)} 条")
        time.sleep(random.uniform(1.0, 2.0))
        return results
    except Exception as e:
        print(f"  [zcygov失败] {keyword}: {e}")
        return []


def deduplicate(items: list) -> list:
    seen = set()
    unique = []
    for item in items:
        key = hashlib.md5(item["title"][:30].encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def collect_all() -> dict:
    results = {}
    for cat in CATEGORIES:
        print(f"\n{'='*40}")
        print(f"采集类别：{cat['icon']} {cat['name']}")
        all_items = []
        for kw in cat["keywords"]:
            r1 = search_ccgp(kw, DAYS_BACK)
            r2 = search_zcygov(kw, DAYS_BACK)
            all_items.extend(r1)
            all_items.extend(r2)
        
        unique = deduplicate(all_items)
        results[cat["id"]] = {"cat": cat, "items": unique[:15]}
        print(f"  → 去重后共 {len(unique)} 条")
    
    return results


def generate_html(results: dict) -> str:
    run_date = datetime.now().strftime("%Y年%m月%d日")
    run_time = datetime.now().strftime("%H:%M")
    total = sum(len(v["items"]) for v in results.values())
    
    # Build category HTML
    cats_html = ""
    for cat_id, data in results.items():
        cat = data["cat"]
        items = data["items"]
        
        if not items:
            rows = '<div class="empty"><p>本次采集暂无该类别招标信息</p></div>'
        else:
            rows = ""
            for i, item in enumerate(items):
                url = item.get("url", "")
                has_url = url.startswith("http")
                title_html = f'<a href="{url}" target="_blank">{item["title"]}</a>' if has_url else item["title"]
                meta_parts = []
                if item.get("buyer"):
                    meta_parts.append(f'<span class="meta"><span class="dot"></span>{item["buyer"]}</span>')
                if item.get("zone"):
                    meta_parts.append(f'<span class="meta"><span class="dot"></span>{item["zone"]}</span>')
                if item.get("budget") and item["budget"] != "未披露":
                    meta_parts.append(f'<span class="meta"><span class="dot"></span>预算：{item["budget"]}</span>')
                if item.get("pub_date"):
                    meta_parts.append(f'<span class="meta"><span class="dot"></span>{item["pub_date"]}</span>')
                meta_parts.append(f'<span class="meta src-tag">{item.get("source","网络来源")}</span>')
                
                link_btn = f'<a href="{url}" target="_blank" class="link-btn">查看原文 →</a>' if has_url else '<span class="link-btn disabled">暂无链接</span>'
                
                rows += f"""
                <div class="item">
                  <div class="item-body">
                    <div class="item-title">{title_html}</div>
                    <div class="item-meta">{"".join(meta_parts)}</div>
                  </div>
                  <div class="item-action">{link_btn}</div>
                </div>"""
        
        cats_html += f"""
        <div class="cat-block" data-cat="{cat_id}">
          <div class="cat-head">
            <span class="cat-icon">{cat['icon']}</span>
            <span class="cat-title">{cat['name']}</span>
            <span class="cat-count">{len(items)} 条</span>
          </div>
          <div class="list">{rows}</div>
        </div>"""
    
    # Tab buttons
    tabs_html = '<button class="tab active" onclick="filterCat(\'all\',this)">全部</button>'
    for cat_id, data in results.items():
        cat = data["cat"]
        n = len(data["items"])
        short = cat["name"].split("/")[0].strip()
        tabs_html += f'<button class="tab" onclick="filterCat(\'{cat_id}\',this)">{cat["icon"]} {short}（{n}）</button>'
    
    # JSON data for client-side filtering
    results_json = json.dumps({
        k: {"cat_id": k, "count": len(v["items"])} for k, v in results.items()
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>招标信息日报 · {run_date}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
:root{{--ink:#1C1C1E;--muted:#8E8E93;--gold:#B8860B;--gold-light:#D4A017;--gold-pale:#FDF8EC;--gold-border:#E8D5A0;--surface:#FAFAF8;--white:#fff;--border:#E5E2D9;--red:#C0392B;--green:#27AE60;--tag-bg:#F0EDE4}}
*{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{font-family:'Noto Sans SC',sans-serif;background:var(--surface);color:var(--ink)}}
.topbar{{background:var(--ink);padding:0 40px;display:flex;align-items:center;justify-content:space-between;height:52px;position:sticky;top:0;z-index:100}}
.logo{{font-family:'Noto Serif SC',serif;font-size:14px;font-weight:600;color:#fff;display:flex;align-items:center;gap:10px}}
.logo::before{{content:'';width:5px;height:18px;background:var(--gold-light);display:block}}
.top-date{{font-size:12px;color:rgba(255,255,255,.45)}}
.hero{{background:var(--ink);padding:40px 40px 56px;position:relative}}
.hero::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent)}}
.hero-inner{{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:40px;align-items:center}}
.hero-title{{font-family:'Noto Serif SC',serif;font-size:clamp(20px,2.8vw,34px);font-weight:700;color:#fff;line-height:1.3;margin-bottom:10px}}
.hero-title span{{color:var(--gold-light)}}
.hero-sub{{font-size:13px;color:rgba(255,255,255,.4);line-height:1.8;max-width:460px}}
.stats{{display:flex;border:1px solid rgba(255,255,255,.1)}}
.stat{{padding:16px 24px;text-align:center;border-right:1px solid rgba(255,255,255,.08)}}
.stat:last-child{{border-right:none}}
.stat-n{{font-family:'Noto Serif SC',serif;font-size:26px;font-weight:700;color:var(--gold-light);display:block}}
.stat-l{{font-size:10px;color:rgba(255,255,255,.3);margin-top:2px;letter-spacing:1px}}
.main{{max-width:1080px;margin:0 auto;padding:28px 40px 60px}}
.sum-bar{{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--border);margin-bottom:24px;flex-wrap:wrap;gap:10px}}
.sum-left{{font-size:13px;color:var(--muted)}}
.sum-left strong{{color:var(--ink);font-weight:500}}
.tabs{{display:flex;gap:4px;flex-wrap:wrap}}
.tab{{padding:5px 13px;font-size:12px;border:1px solid var(--border);background:var(--white);color:var(--muted);cursor:pointer;transition:all .15s}}
.tab.active{{background:var(--ink);color:var(--gold-light);border-color:var(--ink)}}
.tab:hover:not(.active){{border-color:var(--gold);color:var(--gold)}}
.cat-block{{margin-bottom:32px}}
.cat-head{{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:2px solid var(--ink)}}
.cat-icon{{font-size:16px}}
.cat-title{{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600}}
.cat-count{{margin-left:auto;font-size:12px;padding:2px 10px;background:var(--gold-pale);color:var(--gold);border:1px solid var(--gold-border)}}
.list{{border:1px solid var(--border);border-top:none}}
.item{{display:grid;grid-template-columns:1fr auto;gap:14px;padding:14px 18px;border-bottom:1px solid var(--border);background:var(--white);transition:background .15s}}
.item:last-child{{border-bottom:none}}
.item:hover{{background:var(--gold-pale)}}
.item-title{{font-size:14px;font-weight:500;line-height:1.6;margin-bottom:6px}}
.item-title a{{color:var(--ink);text-decoration:none}}
.item-title a:hover{{color:var(--gold)}}
.item-meta{{display:flex;gap:12px;flex-wrap:wrap}}
.meta{{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:3px}}
.dot{{width:3px;height:3px;background:var(--gold);border-radius:50%;flex-shrink:0}}
.src-tag{{background:var(--tag-bg);padding:1px 6px;border-radius:2px}}
.item-action{{display:flex;align-items:center;flex-shrink:0}}
.link-btn{{font-size:12px;color:var(--gold);text-decoration:none;border:1px solid var(--gold-border);padding:4px 12px;white-space:nowrap;transition:all .15s}}
.link-btn:hover{{background:var(--gold);color:#fff}}
.link-btn.disabled{{opacity:.3;cursor:default}}
.empty{{text-align:center;padding:36px;border:1px dashed var(--border);border-top:none;background:var(--white)}}
.empty p{{font-size:13px;color:var(--muted)}}
.footer{{background:var(--ink);color:rgba(255,255,255,.35);text-align:center;padding:32px 40px;font-size:12px;line-height:2}}
.footer strong{{color:var(--gold-light);font-weight:400}}
.print-header{{display:none;text-align:center;padding:40px 0 20px;border-bottom:2px solid var(--ink);margin-bottom:28px}}
.print-header h1{{font-family:'Noto Serif SC',serif;font-size:22px;font-weight:700}}
.print-header p{{font-size:13px;color:var(--muted);margin-top:6px}}
.btn-print{{display:inline-block;margin-top:12px;padding:8px 20px;border:1px solid rgba(255,255,255,.2);color:rgba(255,255,255,.6);font-size:12px;cursor:pointer;background:transparent;font-family:'Noto Sans SC',sans-serif;transition:all .2s}}
.btn-print:hover{{border-color:var(--gold);color:var(--gold-light)}}
@media(max-width:680px){{
  .hero-inner{{display:block}}
  .stats{{display:grid;grid-template-columns:1fr 1fr;margin-top:16px}}
  .main,.topbar,.hero{{padding-left:16px;padding-right:16px}}
  .item{{grid-template-columns:1fr}}
}}
@media print{{
  .topbar,.tabs,.btn-print,.footer{{display:none!important}}
  .print-header{{display:block!important}}
  .main{{padding-top:0}}
}}
</style>
</head>
<body>
<div class="topbar">
  <div class="logo">招标信息智能日报系统</div>
  <div class="top-date">{run_date} {run_time} 自动更新</div>
</div>
<div class="hero">
  <div class="hero-inner">
    <div>
      <div class="hero-title">每日<span>招标信息</span>日报<br>服务端采集 · 数据真实可靠</div>
      <div class="hero-sub">数据直接来自中国政府采购网、采购云平台等官方公开渠道，每天自动更新，无需登录会员</div>
    </div>
    <div class="stats">
      <div class="stat"><span class="stat-n">{total}</span><div class="stat-l">本期总条数</div></div>
      <div class="stat"><span class="stat-n">5</span><div class="stat-l">监控类别</div></div>
      <div class="stat"><span class="stat-n">{DAYS_BACK}天</span><div class="stat-l">采集范围</div></div>
    </div>
  </div>
</div>
<div class="main">
  <div class="print-header">
    <h1>招标信息日报</h1>
    <p>采集日期：{run_date} · 共 {total} 条</p>
  </div>
  <div class="sum-bar">
    <div class="sum-left">本期采集到 <strong>{total}</strong> 条招标信息 &nbsp;·&nbsp; 更新时间：{run_date} {run_time}</div>
    <div class="tabs" id="tabs">{tabs_html}</div>
  </div>
  <div id="results">{cats_html}</div>
</div>
<div class="footer">
  <div>数据来源：<strong>中国政府采购网</strong> · <strong>采购云平台</strong> &nbsp;|&nbsp; 数据为公开招标公告，仅供参考</div>
  <div>由 GitHub Actions 每日 12:00 自动采集生成 &nbsp;·&nbsp; <button class="btn-print" onclick="window.print()">打印 / 保存PDF</button></div>
</div>
<script>
function filterCat(id, el){{
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
  if(el) el.classList.add('active');
  document.querySelectorAll('.cat-block').forEach(b=>{{
    b.style.display = (id==='all' || b.dataset.cat===id) ? 'block' : 'none';
  }});
}}
</script>
</body>
</html>"""


def main():
    print(f"\n{'='*50}")
    print(f"  招标信息采集启动  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  采集范围：近 {DAYS_BACK} 天")
    print(f"{'='*50}\n")

    results = collect_all()
    
    total = sum(len(v["items"]) for v in results.values())
    print(f"\n\n✅ 采集完成，共 {total} 条")

    html = generate_html(results)
    
    # 保存到 index.html（GitHub Pages 入口）
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 已生成 index.html")

    # 同时保存 JSON 数据供调试
    json_data = {
        "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": total,
        "categories": {
            k: {
                "name": v["cat"]["name"],
                "count": len(v["items"]),
                "items": v["items"]
            } for k, v in results.items()
        }
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("✅ 已生成 data.json")


if __name__ == "__main__":
    main()
