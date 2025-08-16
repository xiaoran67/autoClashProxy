import asyncio
import aiohttp
import logging
import os
import re
import time

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 读取订阅文件中的 URL
def read_subscribe_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logging.error(f"未找到订阅文件: {file_path}")
        return []


# 读取 demo.txt（格式：分组行+下属频道行）
def read_demo_file(file_path):
    try:
        group_order = []  # 分组顺序列表
        group_channels = {}  # 分组→频道映射：{分组名: [频道1, 频道2...]}

        with open(file_path, 'r', encoding='utf-8') as f:
            current_group = None
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):  # 跳过空行和注释
                    continue
                # 识别分组行（格式：分组名称,#genre#）
                if '#genre#' in line:
                    current_group = line.split(',#genre#')[0].strip()
                    if current_group and current_group not in group_order:
                        group_order.append(current_group)
                        group_channels[current_group] = []
                # 识别频道行（属于当前分组）
                elif current_group is not None:
                    group_channels[current_group].append(line)

        return group_order, group_channels
    except FileNotFoundError:
        logging.error(f"未找到 demo.txt 文件: {file_path}")
        return [], {}


# 异步获取 URL 内容并测试响应时间
async def fetch_url(session, url):
    start_time = time.time()
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                elapsed_time = time.time() - start_time
                return content, elapsed_time
            logging.warning(f"请求 {url} 失败，状态码: {response.status}")
    except Exception as e:
        logging.error(f"请求 {url} 时发生错误: {e}")
    return None, float('inf')


# 解析 M3U 格式内容
def parse_m3u_content(content):
    channels = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:'):
            info = line.split(',', 1)
            if len(info) == 2:
                metadata = info[0]
                name = info[1]
                tvg_id = re.search(r'tvg-id="([^"]+)"', metadata)
                tvg_name = re.search(r'tvg-name="([^"]+)"', metadata)
                group_title = re.search(r'group-title="([^"]+)"', metadata)
                i += 1
                if i < len(lines):
                    url = lines[i].strip()
                    channel = {
                        'name': name,
                        'url': url,
                        'tvg_id': tvg_id.group(1) if tvg_id else None,
                        'tvg_name': tvg_name.group(1) if tvg_name else None,
                        'group_title': group_title.group(1) if group_title else None,
                        'response_time': float('inf')
                    }
                    channels.append(channel)
        i += 1
    return channels


# 解析 TXT 格式内容
def parse_txt_content(content):
    channels = []
    current_group = None
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if line.endswith('#genre#'):
            current_group = line.replace('#genre#', '').strip()
        elif line:
            parts = line.split(',', 1)
            if len(parts) == 2:
                name, url = parts
                channel = {
                    'name': name,
                    'url': url,
                    'tvg_id': None,
                    'tvg_name': None,
                    'group_title': current_group,
                    'response_time': float('inf')
                }
                channels.append(channel)
    return channels


# 合并并去重频道
def merge_and_deduplicate(channels_list):
    all_channels = []
    for channels in channels_list:
        all_channels.extend(channels)
    unique_channels = []
    url_set = set()
    for channel in all_channels:
        if channel['url'] not in url_set:
            unique_channels.append(channel)
            url_set.add(channel['url'])
    return unique_channels


# 测试每个频道的响应时间
async def test_channel_response_time(session, channel):
    start_time = time.time()
    try:
        async with session.get(channel['url'], timeout=10) as response:
            if response.status == 200:
                elapsed_time = time.time() - start_time
                channel['response_time'] = elapsed_time
    except Exception as e:
        logging.error(f"测试 {channel['url']} 响应时间时发生错误: {e}")
    return channel


# 过滤频道：忽略订阅源分组，仅按 demo.txt 的频道名和分组归属
def filter_channels(channels, group_order, group_channels):
    filtered_channels = []
    for channel in channels:
        channel_name = channel['name']
        # 遍历 demo.txt 中所有分组的目标频道列表
        for group_title, target_channels in group_channels.items():
            if channel_name in target_channels:
                # 强制将频道的分组设为当前分组
                channel['group_title'] = group_title
                filtered_channels.append(channel)
                break  # 一个频道只归属一个分组（若需多分组可删除 break）
    return filtered_channels


# 生成 M3U 文件，增加 EPG 回放支持
def generate_m3u_file(channels, output_path, replay_days=7, custom_sort_order=None):
    # 按分组标题分组
    group_channels = {}
    for channel in channels:
        group_title = channel['group_title'] or ''
        if group_title not in group_channels:
            group_channels[group_title] = []
        group_channels[group_title].append(channel)

    def custom_sort_key(group_title):
        if custom_sort_order and group_title in custom_sort_order:
            return custom_sort_order.index(group_title)
        return float('inf')

    sorted_groups = sorted(group_channels.keys(), key=custom_sort_key)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for group_title in sorted_groups:
            group = group_channels[group_title]
            sorted_group = sorted(group, key=lambda x: x['response_time'])
            if group_title:
                f.write(f'#EXTGRP:{group_title}\n')
            for channel in sorted_group:
                metadata = '#EXTINF:-1'
                if channel['tvg_id']:
                    metadata += f' tvg-id="{channel["tvg_id"]}"'
                if channel['tvg_name']:
                    metadata += f' tvg-name="{channel["tvg_name"]}"'
                if channel['group_title']:
                    clean_group_title = channel["group_title"].strip(',').strip()
                    metadata += f' group-title="{clean_group_title}"'
                replay_url = f'{channel["url"]}&replay=1&days={replay_days}'
                f.write(f'{metadata},{channel["name"]}\n')
                f.write(f'{replay_url}\n')
            f.write('\n')


# 生成 TXT 文件
def generate_txt_file(channels, output_path, custom_sort_order=None):
    # 按分组标题分组
    group_channels = {}
    for channel in channels:
        group_title = channel['group_title'] or ''
        if group_title not in group_channels:
            group_channels[group_title] = []
        group_channels[group_title].append(channel)

    def custom_sort_key(group_title):
        if custom_sort_order and group_title in custom_sort_order:
            return custom_sort_order.index(group_title)
        return float('inf')

    sorted_groups = sorted(group_channels.keys(), key=custom_sort_key)

    with open(output_path, 'w', encoding='utf-8') as f:
        for group_title in sorted_groups:
            group = group_channels[group_title]
            sorted_group = sorted(group, key=lambda x: x['response_time'])
            if group_title:
                f.write(f'{group_title},#genre#\n')
            for channel in sorted_group:
                f.write(f'{channel["name"]},{channel["url"]}\n')
            f.write('\n')


async def main():
    subscribe_file = 'config/subscribe.txt'
    output_m3u = 'output/result.m3u'
    output_txt = 'output/result.txt'
    demo_file = 'config/demo.txt'  # demo.txt 路径

    # 读取 demo.txt：获取分组顺序和分组-频道映射
    group_order, group_channels = read_demo_file(demo_file)
    custom_sort_order = group_order  # 按 demo.txt 分组顺序排序

    # 确保输出目录存在
    output_dir = os.path.dirname(output_m3u)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 读取订阅文件
    urls = read_subscribe_file(subscribe_file)
    if not urls:
        logging.error("订阅文件中没有有效的 URL。")
        return

    # 异步获取所有 URL 的内容
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

    all_channels = []
    for content, _ in results:
        if content:
            if '#EXTM3U' in content:
                channels = parse_m3u_content(content)
            else:
                channels = parse_txt_content(content)
            all_channels.append(channels)

    # 合并并去重频道
    unique_channels = merge_and_deduplicate(all_channels)

    # 测试每个频道的响应时间
    async with aiohttp.ClientSession() as session:
        tasks = [test_channel_response_time(session, channel) for channel in unique_channels]
        unique_channels = await asyncio.gather(*tasks)

    # 过滤频道：忽略订阅源分组，按 demo.txt 归属
    filtered_channels = filter_channels(unique_channels, group_order, group_channels)

    # 生成文件（按 demo.txt 分组顺序）
    generate_m3u_file(filtered_channels, output_m3u, custom_sort_order=custom_sort_order)
    generate_txt_file(filtered_channels, output_txt, custom_sort_order=custom_sort_order)

    logging.info("成功生成 M3U 和 TXT 文件。")


if __name__ == '__main__':
    asyncio.run(main())
