import requests
import time
import datetime
import random
import os
from dotenv import load_dotenv
load_dotenv()

class HakoneEkidenMonitor:
    def __init__(self):
        # 多关键词支持
        self.keywords = ["箱根驿传", "镖人", "浙大"]
        self.api_url = "https://api.bilibili.com/x/web-interface/search/type"

        # 【重要】填入 Cookie
        self.cookie = os.environ.get("BILIBILI_COOKIE") 
        
        if not self.cookie:
            print("❌ 错误：未检测到 Cookie！请检查 .env 文件或 GitHub Secrets 设置。")

        # 模拟浏览器头部，防止被B站拦截
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://search.bilibili.com/",
            "Cookie": self.cookie or ""  # 带上身份证
        }

    def fetch_videos(self, order_type, limit, keyword=None):
        """
        获取视频列表（可指定 keyword）
        :param order_type: 排序方式 ('pubdate'/'click'/...)
        :param limit: 获取数量
        :param keyword: 搜索关键词，若为 None 则使用第一个关键词作为默认
        """
        kw = keyword or (self.keywords[0] if self.keywords else "")
        params = {
            "search_type": "video",
            "keyword": kw,
            "order": order_type,
            "page": 1,
            "page_size": 20
        }

        try:
            # 打印正在请求的 URL，方便调试
            print(f"📡 请求 B站接口 (Keyword: {kw} | Order: {order_type})...")
            response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)

            # 检查 HTTP 状态码
            if response.status_code != 200:
                print(f"❌ HTTP 请求失败，状态码: {response.status_code}")
                return []

            # 尝试解析 JSON
            try:
                data = response.json()
            except ValueError:
                print("❌ 解析失败：B站返回的不是 JSON 数据。可能是被拦截了，请检查 Cookie 是否过期。")
                print(f"返回内容前100字: {response.text[:100]}")  # 打印出来看看是啥
                return []

            # 检查业务状态码
            if data['code'] != 0:
                print(f"❌ API 业务报错: {data.get('message')}")
                return []

            video_list = []
            if 'data' in data and 'result' in data['data']:
                items = data['data']['result']
                for item in items:
                    if item.get('type') == 'video':
                        video_info = {
                            "title": item['title'].replace('<em class="keyword">', '').replace('</em>', ''),
                            "author": item.get('author', ''),
                            "play": item.get('play', 0),
                            "date": datetime.datetime.fromtimestamp(item.get('pubdate', 0)).strftime('%Y-%m-%d'),
                            "url": f"https://www.bilibili.com/video/{item.get('bvid')}",
                            "bvid": item.get('bvid')
                        }
                        video_list.append(video_info)

            print(f"✅ 成功获取 {len(video_list)} 条数据 (关键词: {kw})")
            return video_list[:limit]

        except Exception as e:
            print(f"❌ 发生未知错误: {e}")
            return []

    def _parse_count(self, val):
        """把 API 返回的播放/点击/收藏等文本数值归一化为整数。"""
        if val is None:
            return 0
        try:
            if isinstance(val, (int, float)):
                return int(val)
            s = str(val).strip()
            if '亿' in s:
                return int(float(s.replace('亿', '')) * 100000000)
            if '万' in s:
                return int(float(s.replace('万', '')) * 10000)
            s2 = ''.join(ch for ch in s if (ch.isdigit() or ch == '.'))
            if s2 == '':
                return 0
            return int(float(s2))
        except Exception:
            return 0

    def fetch_week_videos_top_by_click(self, limit=10, max_pages=10, page_size=50, keyword=None):
        """
        抓取最近一周（7天）内所有与关键词匹配的视频，按播放量排序并返回前 limit 个。
        :param keyword: 指定搜索关键词
        """
        kw = keyword or (self.keywords[0] if self.keywords else "")
        end_time = int(time.time())
        start_time = end_time - 7 * 24 * 60 * 60

        collected = []
        seen = set()

        for page in range(1, max_pages + 1):
            params = {
                "search_type": "video",
                "keyword": kw,
                "order": 'pubdate',
                "page": page,
                "page_size": page_size
            }

            try:
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    break
                data = response.json()
                if data.get('code') != 0:
                    break
                items = data.get('data', {}).get('result', [])
                if not items:
                    break

                # 判断本页是否全部早于 start_time，用于提前停止
                all_older = True
                for item in items:
                    if item.get('type') != 'video':
                        continue
                    pub = item.get('pubdate', 0)
                    if pub >= start_time:
                        all_older = False
                        bvid = item.get('bvid')
                        if not bvid or bvid in seen:
                            continue
                        seen.add(bvid)
                        play = self._parse_count(item.get('play') or item.get('click'))
                        video_info = {
                            'title': item.get('title', '').replace('<em class="keyword">', '').replace('</em>', ''),
                            'author': item.get('author', ''),
                            'play': play,
                            'date': datetime.datetime.fromtimestamp(pub).strftime('%Y-%m-%d'),
                            'url': f"https://www.bilibili.com/video/{bvid}",
                            'bvid': bvid,
                            'click': self._parse_count(item.get('click') or item.get('play')),
                            'scores': self._parse_count(item.get('reviews')),
                            'stow': self._parse_count(item.get('favorites'))
                        }
                        collected.append(video_info)

                if all_older:
                    break

            except Exception:
                break

            # 每页请求间加入短随机延时，防封控
            time.sleep(random.uniform(0.5, 1.5))

        collected.sort(key=lambda x: x.get('play', 0), reverse=True)
        return collected[:limit]

    def fetch_top_click_candidates(self, candidate_count=20, max_pages=5, page_size=50, keyword=None):
        """
        按 click 排序抓取（API order=click），返回去重后的前 candidate_count 条候选，用于后续评分。
        :param keyword: 指定搜索关键词
        """
        kw = keyword or (self.keywords[0] if self.keywords else "")
        collected = []
        seen = set()
        page = 1
        while len(collected) < candidate_count and page <= max_pages:
            params = {
                "search_type": "video",
                "keyword": kw,
                "order": 'click',
                "page": page,
                "page_size": page_size
            }
            try:
                response = requests.get(self.api_url, headers=self.headers, params=params, timeout=10)
                if response.status_code != 200:
                    break
                data = response.json()
                if data.get('code') != 0:
                    break
                items = data.get('data', {}).get('result', [])
                if not items:
                    break
                for item in items:
                    if item.get('type') != 'video':
                        continue
                    bvid = item.get('bvid')
                    if not bvid or bvid in seen:
                        continue
                    seen.add(bvid)
                    play = self._parse_count(item.get('play') or item.get('click'))
                    info = {
                        'title': item.get('title', '').replace('<em class="keyword">', '').replace('</em>', ''),
                        'author': item.get('author', ''),
                        'play': play,
                        'date': datetime.datetime.fromtimestamp(item.get('pubdate', 0)).strftime('%Y-%m-%d'),
                        'url': f"https://www.bilibili.com/video/{bvid}",
                        'bvid': bvid,
                        'click': self._parse_count(item.get('click') or item.get('play')),
                        'scores': self._parse_count(item.get('scores') or item.get('reviews')),
                        'stow': self._parse_count(item.get('stow') or item.get('favorites'))
                    }
                    collected.append(info)
                    if len(collected) >= candidate_count:
                        break
                page += 1
            except Exception:
                break

            # 每页请求间加入短随机延时，防封控
            time.sleep(random.uniform(0.5, 1.5))

        collected.sort(key=lambda x: x.get('click', 0), reverse=True)
        return collected[:candidate_count]

    def compute_weighted_hot(self, candidates, weights=(0.2, 0.5, 0.3), top_n=5):
        """
        对候选集依据 click, scores, stow 三个指标按 weights 加权，归一化后计算总分并返回 top_n。
        weights: (w_click, w_scores, w_stow)
        """
        if not candidates:
            return []

        clicks = [c.get('click', 0) for c in candidates]
        scores = [c.get('scores', 0) for c in candidates]
        stows = [c.get('stow', 0) for c in candidates]

        def normalize(arr):
            mn = min(arr)
            mx = max(arr)
            if mx == mn:
                return [1.0 for _ in arr]
            return [(v - mn) / (mx - mn) for v in arr]

        n_click = normalize(clicks)
        n_scores = normalize(scores)
        n_stow = normalize(stows)

        w_click, w_scores, w_stow = weights

        for i, c in enumerate(candidates):
            score = n_click[i] * w_click + n_scores[i] * w_scores + n_stow[i] * w_stow
            c['_weighted_score'] = score

        candidates.sort(key=lambda x: x.get('_weighted_score', 0), reverse=True)
        return candidates[:top_n]

    def run(self):
        print(f"🏃 开始执行任务：搜索关键词 {self.keywords} ...")

        if not self.cookie or "你的B站Cookie" in (self.cookie or ""):
            print("⚠️ 警告：你还没有填写 Cookie，获取热门视频极大概率会失败！")

        all_results = {}

        for kw in self.keywords:
            print(f"\n===== 关键词：{kw} =====")
            # 1. 获取 本周发布并按播放量排序的最新视频
            print("\n--- 正在获取本周所有相关视频并按播放量排序，取前10 ---")
            new_videos = self.fetch_week_videos_top_by_click(limit=10, keyword=kw)

            # 请求间随机延时，减低风控风险
            time.sleep(random.uniform(3, 6))

            # 2. 获取 按 click 排序的候选视频，按指标归一化加权后取前10
            print("\n--- 正在获取 click 排序候选并计算加权得分，取 top10 ---")
            candidates = self.fetch_top_click_candidates(candidate_count=20, keyword=kw)
            hot_candidates = self.compute_weighted_hot(candidates, weights=(0.2, 0.5, 0.3), top_n=10)

            # 去掉与本周最新视频重复的项，最终取前5
            new_ids = {v['bvid'] for v in new_videos}
            old_videos = [v for v in hot_candidates if v['bvid'] not in new_ids]
            old_videos = old_videos[:5]

            all_results[kw] = {"new": new_videos, "old": old_videos}

            print(f"✅ 关键词 [{kw}] 抓取完成，暂停一段时间后继续下一个关键词...")
            # 切换关键词时再做较长随机延时
            time.sleep(random.uniform(5, 10))

        # 生成汇总报告（包含所有关键词）
        self.generate_report(all_results)

    def generate_report(self, all_results):
        report_lines = []
        report_lines.append(f"# 🎽 B站视频监测周报 ({datetime.date.today()})\n")

        total_new = sum(len(v["new"]) for v in all_results.values())
        total_old = sum(len(v["old"]) for v in all_results.values())
        report_lines.append(f"本次共监测关键词：{', '.join(all_results.keys())}")
        report_lines.append(f"本周为您汇总了 **{total_new}** 个新视频和 **{total_old}** 个经典回顾。\n")

        for kw, data in all_results.items():
            new_list = data.get('new', [])
            old_list = data.get('old', [])

            report_lines.append(f"## 🔎 关键词：{kw}\n")

            report_lines.append("### 🆕 本周热门发布 (Top 10 by 播放量)")
            report_lines.append("| 发布日期 | 标题 | UP主 | 播放量 |")
            report_lines.append("|---|---|---|---|")
            if not new_list:
                report_lines.append("| - | 获取失败或无数据 | - | - |")
            for v in new_list:
                title_safe = v.get('title', '')
                title_safe = title_safe.replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')
                report_lines.append(f"| {v['date']} | [{title_safe}]({v['url']}) | {v['author']} | {v['play']} |")

            report_lines.append("\n### 🔥 经典/热门 (Hot 5, 基于 click/scores/stow 加权排序)")
            report_lines.append("| 发布日期 | 标题 | UP主 | 播放量 | 得分 |")
            report_lines.append("|---|---|---|---|---|")
            if not old_list:
                report_lines.append("| - | 获取失败或无数据 | - | - | - |")
            for v in old_list:
                title_safe = v.get('title', '')
                title_safe = title_safe.replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ')
                score = v.get('_weighted_score')
                score_str = f"{score:.3f}" if score is not None else "-"
                report_lines.append(f"| {v['date']} | [{title_safe}]({v['url']}) | {v['author']} | {v.get('play', 0)} | {score_str} |")

            report_lines.append("\n---\n")

        content = "\n".join(report_lines)

        filename = "B站视频监测周报.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        print("-" * 30)
        print(f"✅ 汇总完成！文件已生成: {filename}")
        print("-" * 30)


if __name__ == "__main__":
    bot = HakoneEkidenMonitor()
    bot.run()