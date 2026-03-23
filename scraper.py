#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
招标信息采集器 v2 - 多平台、多关键词、翻页采集
数据来源：
  1. 中国政府采购网 ccgp.gov.cn（官方）
  2. 采购云平台 zcygov.cn（官方）
  3. 必联网 bidcenter.com.cn（搜索结果公开）
  4. 中国招标投标公共服务平台 bids.gov.cn（官方）
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
}

DAYS_BACK = int(os.environ.get("DAYS_BACK", "30"))

# ══════════════════════════════════════════════
#  关键词配置（大幅扩展）
# ══════════════════════════════════════════════
CATEGORIES = [
    {
        "id": "smoke",
        "icon": "🚬",
        "name": "烟草吸烟室 / 吸烟环境",
        "keywords": [
            "文明吸烟环境",
            "烟草 吸烟室",
            "吸烟亭",
            "室内吸烟室",
            "烟草公司 吸烟",
            "吸烟环境建设",
            "吸烟室采购",
            "禁烟室",
            "烟草局 吸烟",
        ]
    },
    {
        "id": "tobacco",
        "icon": "🏢",
        "name": "烟草公司相关采购",
        "keywords": [
            "烟草公司采购",
            "烟草局采购",
            "中烟 招标",
            "烟草 招标公告",
            "烟草专卖局",
            "烟草集团采购",
            "省烟草公司",
            "市烟草公司",
        ]
    },
    {
        "id": "box",
        "icon": "📦",
        "name": "集装箱厢房 / 活动房",
        "keywords": [
            "集装箱厢房",
            "住人集装箱",
            "集装箱活动房",
            "集装箱板房",
            "集装箱宿舍",
            "集装箱办公室",
            "集装箱房屋",
            "活动板房",
            "移动板房",
            "临时板房",
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
            "分类垃圾房",
            "垃圾中转站",
            "环保垃圾房",
            "垃圾收集亭",
            "果皮箱",
            "垃圾桶采购",
            "垃圾分类亭",
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
            "公共厕所采购",
            "生态公厕",
            "一体化公厕",
            "厕所革命",
            "移动卫生间",
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
        print(f"    [请求失败] {url[:60]}... → {e}")
        return None


def sleep():
    time.sleep(random.uniform(1.5, 3.0))


# ══════════════════════════════════════════════
#  数据源 1：中国政府采购网（翻2页）
# ══════════════════════════════════════════════
def search_ccgp(keyword: str, days: int = 30) -> list:
    now = datetime.now()
    start = now - timedelta(days=days)
    results = []

    for page in range(1, 3):  # 第1、2页
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
        items = soup.select("ul.vT-srch-result-list-bid li")
        if not items:
            break

        for li in items:
            a = li.select_one("a")
            if not a:
                continue
            title = a.get_text(" ", strip=True)
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
                elif "Area" in cls or "area" in cls or "Zone" in cls:
                    zone = txt
                elif "date" in cls.lower() or "time" in cls.lower():
                    pub_date = txt

            results.append({
                "title": title, "buyer": buyer, "zone": zone,
                "budget": "未披露", "pub_date": pub_date,
                "source": "中国政府采购网", "url": href,
            })
        sleep()

    print(f"  [ccgp] '{keyword}' → {len(results)} 条")
    return results


# ══════════════════════════════════════════════
#  数据源 2：采购云平台
# ══════════════════════════════════════════════
def search_zcygov(keyword: str) -> list:
    results = []
    try:
        url = "https://www.zcygov.cn/search/search-purchase-announcement"
        for page in range(1, 3):
            r = safe_get(url, params={"keyword": keyword, "currentPage": page, "pageSize": 10})
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
                    "budget": "未披露",
                    "pub_date": str(item.get("publishTime", ""))[:10],
                    "source": "采购云平台",
                    "url": item.get("url") or item.get("detailUrl", ""),
                })
            sleep()
    except Exception as e:
        print(f"  [zcygov失败] {keyword}: {e}")
    print(f"  [zcygov] '{keyword}' → {len(results)} 条")
    return results


# ══════════════════════════════════════════════
#  数据源 3：必联网 bidcenter
# ══════════════════════════════════════════════
def search_bidcenter(keyword: str) -> list:
    results = []
    try:
        url = f"https://www.bidcenter.com.cn/search/?keyword={quote(keyword)}&page=1"
        r = safe_get(url)
        if not r:
            return results
        soup = BeautifulSoup(r.text, "html.parser")

        # 尝试多种选择器
        selectors = [
            "div.search-list-item", "div.result-item",
            "li.bid-item", "div.list-item",
            "a[href*='/news-']",
        ]
        found = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                break

        for el in found[:10]:
            if el.name == "a":
                title = el.get_text(strip=True)
                href = el.get("href", "")
            else:
                a = el.select_one("a")
                if not a:
                    continue
                title = a.get_text(strip=True)
                href = a.get("href", "")

            if not title or len(title) < 6:
                continue
            if not any(w in title for w in ["招标","采购","公告","竞争","磋商","询价"]):
                continue
            if not href.startswith("http"):
                href = "https://www.bidcenter.com.cn" + href

            date_el = el.select_one(".time, .date, span[class*='date'], span[class*='time']") if el.name != "a" else None
            pub_date = date_el.get_text(strip=True) if date_el else ""

            results.append({
                "title": title, "buyer": "", "zone": "",
                "budget": "未披露", "pub_date": pub_date,
                "source": "必联网", "url": href,
            })
        sleep()
    except Exception as e:
        print(f"  [bidcenter失败] {keyword}: {e}")
    print(f"  [bidcenter] '{keyword}' → {len(results)} 条")
    return results


# ══════════════════════════════════════════════
#  数据源 4：招标投标公共服务平台 bids.gov.cn
# ══════════════════════════════════════════════
def search_bids_gov(keyword: str) -> list:
    results = []
    try:
        url = "https://search.bids.gov.cn/query/search"
        r = safe_get(url, params={"keyword": keyword, "pageNo": 1, "pageSize": 10, "sort": "time"})
        if not r:
            return results
        try:
            data = r.json()
            items = (data.get("data") or {}).get("list") or []
            for item in items:
                title = item.get("title") or item.get("projectName", "")
                if not title:
                    continue
                results.append({
                    "title": title,
                    "buyer": item.get("tenderee") or item.get("buyerName", ""),
                    "zone": item.get("area") or item.get("province", ""),
                    "budget": "未披露",
                    "pub_date": str(item.get("publishTime", ""))[:10],
                    "source": "招标投标公共服务平台",
                    "url": item.get("url") or item.get("detailUrl", ""),
                })
        except Exception:
            # HTML fallback
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.select("a[href]")[:10]:
                title = a.get_text(strip=True)
                if len(title) > 8 and any(w in title for w in ["招标","采购","公告"]):
                    results.append({
                        "title": title, "buyer": "", "zone": "",
                        "budget": "未披露", "pub_date": "",
                        "source": "招标投标公共服务平台",
                        "url": a.get("href", ""),
                    })
        sleep()
    except Exception as e:
        print(f"  [bids.gov失败] {keyword}: {e}")
    print(f"  [bids.gov] '{keyword}' → {len(results)} 条")
    return results


# ══════════════════════════════════════════════
#  去重
# ══════════════════════════════════════════════
def dedup(items: list) -> list:
    seen = set()
    out = []
    for item in items:
        key = hashlib.md5(item["title"][:25].encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ══════════════════════════════════════════════
#  主采集
# ══════════════════════════════════════════════
def collect_all() -> dict:
    results = {}
    for cat in CATEGORIES:
        print(f"\n{'═'*45}")
        print(f"  {cat['icon']} {cat['name']}")
        print(f"{'═'*45}")
        all_items = []
        for kw in cat["keywords"]:
            print(f"\n  关键词：「{kw}」")
            all_items += search_ccgp(kw, DAYS_BACK)
            all_items += search_zcygov(kw)
            all_items += search_bidcenter(kw)
            all_items += search_bids_gov(kw)

        unique = dedup(all_items)
        print(f"\n  ✅ 去重后共 {len(unique)} 条（原始 {len(all_items)} 条）")
        results[cat["id"]] = {"cat": cat, "items": unique[:30]}  # 每类最多30条
    return results


# ══════════════════════════════════════════════
#  生成 HTML 网页
# ══════════════════════════════════════════════
def generate_html(results: dict) -> str:
    run_date = datetime.now().strftime("%Y年%m月%d日")
    run_time = datetime.now().strftime("%H:%M")
    total = sum(len(v["items"]) for v in results.values())

    cats_html = ""
    for cat_id, data in results.items():
        cat = data["cat"]
        items = data["items"]

        if not items:
            rows = '<div class="empty"><p>本次采集暂无该类别招标信息，明天自动更新</p></div>'
        else:
            rows = ""
            for item in items:
                url = item.get("url", "")
                has_url = url.startswith("http")
                title_html = f'<a href="{url}" target="_blank">{item["title"]}</a>' if has_url else item["title"]
                metas = []
                if item.get("buyer"):
                    metas.append(f'<span class="meta"><span class="dot"></span>{item["buyer"]}</span>')
                if item.get("zone"):
                    metas.append(f'<span class="meta"><span class="dot"></span>{item["zone"]}</span>')
                if item.get("budget") and item["budget"] != "未披露":
                    metas.append(f'<span class="meta"><span class="dot"></span>预算：{item["budget"]}</span>')
                if item.get("pub_date"):
                    metas.append(f'<span class="meta"><span class="dot"></span>{item["pub_date"]}</span>')
                metas.append(f'<span class="meta src">{item.get("source","网络")}</span>')
                link = f'<a href="{url}" target="_blank" class="link-btn">查看原文 →</a>' if has_url else '<span class="link-btn dim">暂无链接</span>'
                rows += f"""<div class="item">
  <div class="ib"><div class="it">{title_html}</div><div class="im">{"".join(metas)}</div></div>
  <div class="ia">{link}</div>
</div>"""

        cats_html += f"""<div class="cb" data-cat="{cat_id}">
<div class="ch"><span class="ci">{cat['icon']}</span><span class="ct">{cat['name']}</span><span class="cc">{len(items)} 条</span></div>
<div class="cl">{rows}</div></div>"""

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
.he{{background:var(--ink);padding:40px 40px 56px;position:relative}}
.he::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,var(--go),transparent)}}
.hi{{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:1fr auto;gap:40px;align-items:center}}
.ht{{font-family:'Noto Serif SC',serif;font-size:clamp(20px,2.8vw,34px);font-weight:700;color:#fff;line-height:1.3;margin-bottom:10px}}
.ht span{{color:var(--gl)}}
.hs{{font-size:13px;color:rgba(255,255,255,.4);line-height:1.8;max-width:460px}}
.sr{{display:flex;border:1px solid rgba(255,255,255,.1)}}
.sb{{padding:16px 24px;text-align:center;border-right:1px solid rgba(255,255,255,.08)}}
.sb:last-child{{border-right:none}}
.sn{{font-family:'Noto Serif SC',serif;font-size:26px;font-weight:700;color:var(--gl);display:block}}
.sl{{font-size:10px;color:rgba(255,255,255,.3);margin-top:2px;letter-spacing:1px}}
.mn{{max-width:1080px;margin:0 auto;padding:28px 40px 60px}}
.smb{{display:flex;align-items:center;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--bd);margin-bottom:24px;flex-wrap:wrap;gap:10px}}
.sml{{font-size:13px;color:var(--mu)}} .sml strong{{color:var(--ink);font-weight:500}}
.ts{{display:flex;gap:4px;flex-wrap:wrap}}
.tab{{padding:5px 13px;font-size:12px;border:1px solid var(--bd);background:var(--wh);color:var(--mu);cursor:pointer;transition:all .15s}}
.tab.active{{background:var(--ink);color:var(--gl);border-color:var(--ink)}}
.tab:hover:not(.active){{border-color:var(--go);color:var(--go)}}
.cb{{margin-bottom:32px}}
.ch{{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:2px solid var(--ink)}}
.ci{{font-size:15px}}.ct{{font-family:'Noto Serif SC',serif;font-size:15px;font-weight:600}}
.cc{{margin-left:auto;font-size:12px;padding:2px 10px;background:var(--gp);color:var(--go);border:1px solid var(--gb)}}
.cl{{border:1px solid var(--bd);border-top:none}}
.item{{display:grid;grid-template-columns:1fr auto;gap:14px;padding:14px 18px;border-bottom:1px solid var(--bd);background:var(--wh);transition:background .15s}}
.item:last-child{{border-bottom:none}}.item:hover{{background:var(--gp)}}
.it{{font-size:14px;font-weight:500;line-height:1.6;margin-bottom:5px}}
.it a{{color:var(--ink);text-decoration:none}}.it a:hover{{color:var(--go)}}
.im{{display:flex;gap:12px;flex-wrap:wrap}}
.meta{{font-size:12px;color:var(--mu);display:flex;align-items:center;gap:3px}}
.dot{{width:3px;height:3px;background:var(--go);border-radius:50%;flex-shrink:0}}
.src{{background:var(--tg);padding:1px 6px;border-radius:2px}}
.ia{{display:flex;align-items:center;flex-shrink:0}}
.link-btn{{font-size:12px;color:var(--go);text-decoration:none;border:1px solid var(--gb);padding:4px 12px;white-space:nowrap;transition:all .15s}}
.link-btn:hover{{background:var(--go);color:#fff}}.link-btn.dim{{opacity:.3;cursor:default}}
.empty{{text-align:center;padding:36px;border:1px dashed var(--bd);border-top:none;background:var(--wh)}}
.empty p{{font-size:13px;color:var(--mu)}}
.ft{{background:var(--ink);color:rgba(255,255,255,.3);text-align:center;padding:28px 40px;font-size:12px;line-height:2}}
.ft strong{{color:var(--gl);font-weight:400}}
@media(max-width:680px){{.hi{{display:block}}.sr{{display:grid;grid-template-columns:1fr 1fr;margin-top:16px}}.mn,.tb,.he{{padding-left:16px;padding-right:16px}}.item{{grid-template-columns:1fr}}}}
@media print{{.tb,.ts,.ft{{display:none!important}}.mn{{padding-top:0}}}}
</style>
</head>
<body>
<div class="tb"><div class="lo">招标信息智能日报系统</div><div class="td">{run_date} {run_time} 自动更新</div></div>
<div class="he"><div class="hi">
  <div>
    <div class="ht">每日<span>招标信息</span>日报<br>服务端采集 · 数据真实可靠</div>
    <div class="hs">数据直接来自中国政府采购网、必联网、采购云平台、招标投标公共服务平台等官方公开渠道，每天 12:00 自动更新</div>
  </div>
  <div class="sr">
    <div class="sb"><span class="sn">{total}</span><div class="sl">本期总条数</div></div>
    <div class="sb"><span class="sn">4</span><div class="sl">数据来源</div></div>
    <div class="sb"><span class="sn">{DAYS_BACK}天</span><div class="sl">采集范围</div></div>
  </div>
</div></div>
<div class="mn">
  <div class="smb">
    <div class="sml">本期采集到 <strong>{total}</strong> 条招标信息 &nbsp;·&nbsp; 更新时间：{run_date} {run_time}</div>
    <div class="ts" id="tabs">{tabs}</div>
  </div>
  <div id="res">{cats_html}</div>
</div>
<div class="ft">
  数据来源：<strong>中国政府采购网</strong> · <strong>必联网</strong> · <strong>采购云平台</strong> · <strong>招标投标公共服务平台</strong><br>
  每天北京时间 12:00 由 GitHub Actions 自动采集 · 数据均为公开招标公告，仅供参考
</div>
<script>
function fc(id,el){{
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));
  if(el)el.classList.add('active');
  document.querySelectorAll('.cb').forEach(b=>b.style.display=(id==='all'||b.dataset.cat===id)?'block':'none');
}}
</script>
</body>
</html>"""


def main():
    print(f"\n{'═'*50}")
    print(f"  招标信息采集 v2  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  采集范围：近 {DAYS_BACK} 天  |  数据来源：4个平台")
    print(f"{'═'*50}")

    results = collect_all()
    total = sum(len(v["items"]) for v in results.values())
    print(f"\n\n✅ 采集完成，共 {total} 条")

    html = generate_html(results)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 已生成 index.html")

    json_data = {
        "run_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total": total,
        "categories": {
            k: {"name": v["cat"]["name"], "count": len(v["items"]), "items": v["items"]}
            for k, v in results.items()
        }
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print("✅ 已生成 data.json")


if __name__ == "__main__":
    main()
