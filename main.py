import requests
import time
import datetime
import random
import os
from dotenv import load_dotenv
load_dotenv()

class HakoneEkidenMonitor:
    def __init__(self):
        self.keyword = "箱根驿传"
        self.api_url = "https://api.bilibili.com/x/web-interface/search/type"

        # 【重要】填入 Cookie
        self.cookie = os.environ.get("BILIBILI_COOKIE") 
        
        if not self.cookie:
            print("❌ 错误：未检测到 Cookie！请检查 .env 文件或 GitHub Secrets 设置。")

        # 模拟浏览器头部，防止被B站拦截
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://search.bilibili.com/",
            "Cookie": self.cookie  # 带上身份证
        }

    def fetch_videos(self, order_type, limit):
        """
        获取视频列表
        :param order_type: 排序方式 ('pubdate': 最新发布, 'click': 最多播放, 'scores': 最多评论, 'stow': 最多收藏, 'damku': 最多弹幕, 'default': 综合排序)
        :param limit: 获取数量
        """
        params = {
            "search_type": "video",
            "keyword": self.keyword,
            "order": order_type,
            "page": 1,
            "page_size": 20
        }

        try:
            # 打印正在请求的 URL，方便调试
            print(f"📡 请求 B站接口 (Order: {order_type})...")

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
                print(f"❌ API 业务报错: {data['message']}")
                return []

            video_list = []
            if 'data' in data and 'result' in data['data']:
                items = data['data']['result']
                for item in items:
                    # 只有当 type 为 video 时才提取（有时候会混入其他内容）
                    if item.get('type') == 'video':
                        video_info = {
                            "title": item['title'].replace('<em class="keyword">', '').replace('</em>', ''),
                            "author": item['author'],
                            "play": item['play'],
                            # 处理时间戳，防止报错
                            "date": datetime.datetime.fromtimestamp(item['pubdate']).strftime('%Y-%m-%d'),
                            "url": f"https://www.bilibili.com/video/{item['bvid']}",
                            "bvid": item['bvid']
                        }
                        video_list.append(video_info)

            print(f"✅ 成功获取 {len(video_list)} 条数据")
            return video_list[:limit]

        except Exception as e:
            print(f"❌ 发生未知错误: {e}")
            return []

    def run(self):
        print(f"🏃 开始执行任务：搜索关键词 [{self.keyword}]...")

        if "你的B站Cookie" in self.cookie:
            print("⚠️ 警告：你还没有填写 Cookie，获取热门视频极大概率会失败！")

        # 1. 获取 10 个最新视频
        print("\n--- 正在获取最新视频 (New) ---")
        new_videos = self.fetch_videos(order_type='pubdate', limit=10)

        # 【关键修改】增加延时，防止请求太快
        sleep_time = random.uniform(5, 8)
        print(f"\n💤 休息 {sleep_time:.1f} 秒，防止被 B站封锁...")
        time.sleep(sleep_time)

        # 2. 获取 5 个经典/热门视频
        print("\n--- 正在获取热门旧视频 (Hot) ---")
        raw_old_videos = self.fetch_videos(order_type='scores', limit=10)

        # 3. 数据处理：去重与筛选
        new_ids = {v['bvid'] for v in new_videos}

        old_videos = []
        for v in raw_old_videos:
            if v['bvid'] not in new_ids:
                old_videos.append(v)
            if len(old_videos) >= 5:
                break

        # 4. 生成汇总报告
        self.generate_report(new_videos, old_videos)

    def generate_report(self, new_list, old_list):
        report_lines = []
        report_lines.append(f"# 🎽 箱根驿传周报 ({datetime.date.today()})")
        report_lines.append(f"本周为您汇总了 **{len(new_list)}** 个新视频和 **{len(old_list)}** 个经典回顾。\n")

        report_lines.append("## 🆕 最新发布 (New 10)")
        report_lines.append("| 发布日期 | 标题 | UP主 | 播放量 |")
        report_lines.append("|---|---|---|---|")
        for v in new_list:
            report_lines.append(f"| {v['date']} | [{v['title']}]({v['url']}) | {v['author']} | {v['play']} |")

        report_lines.append("\n## 🔥 经典/热门 (Hot 5)")
        report_lines.append("| 发布日期 | 标题 | UP主 | 播放量 |")
        report_lines.append("|---|---|---|---|")
        if not old_list:
            report_lines.append("| - | 获取失败或无数据 | - | - |")
        for v in old_list:
            report_lines.append(f"| {v['date']} | [{v['title']}]({v['url']}) | {v['author']} | {v['play']} |")

        content = "\n".join(report_lines)

        filename = "箱根驿传_report.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        print("-" * 30)
        print(f"✅ 汇总完成！文件已生成: {filename}")
        print("-" * 30)


if __name__ == "__main__":
    bot = HakoneEkidenMonitor()
    bot.run()