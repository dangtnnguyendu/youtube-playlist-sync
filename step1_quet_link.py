#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime

try:
    import yt_dlp
except ImportError:
    print("❌ Chưa cài đặt yt-dlp. Hãy chạy lệnh: pip install -U yt-dlp")
    sys.exit(1)

DATA_FILE = "playlist_data.json"
PLAYLISTS_TXT = "playlists.txt"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_playlist_url(url: str) -> str:
    url = url.strip()
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    if "list" in qs and qs["list"]:
        return f"https://www.youtube.com/playlist?list={qs['list'][0]}"
    return url


def read_playlists_txt(filepath: str = PLAYLISTS_TXT) -> list[str]:
    if not os.path.exists(filepath):
        return []
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            clean = line.strip()
            if not clean or clean.startswith("#"):
                continue
            urls.append(normalize_playlist_url(clean))
    return urls


def load_data(filepath: str = DATA_FILE) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("meta", {"updated_at": now_iso(), "playlists": [], "total_videos": 0})
        data.setdefault("scanned_ids", [])
        data.setdefault("videos", {})
        return data
    return {
        "meta": {
            "updated_at": now_iso(),
            "playlists": [],
            "total_videos": 0,
        },
        "scanned_ids": [],
        "videos": {},
    }


def save_data(data: dict, filepath: str = DATA_FILE) -> None:
    data["meta"]["updated_at"] = now_iso()
    data["meta"]["total_videos"] = len(data["videos"])
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_all_playlist_entries(playlist_url: str) -> tuple[str, list[dict]]:
    ydl_opts = {
        "extract_flat": "in_playlist",
        "noplaylist": False,
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        if not info:
            return "", []
        playlist_title = info.get("title") or playlist_url
        entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
        return playlist_title, entries


def main():
    parser = argparse.ArgumentParser(description="Bước 1: Quét toàn bộ link video từ YouTube Playlist vào kho JSON")
    parser.add_argument("-p", "--playlists", nargs="+", help="Một hoặc nhiều link YouTube Playlist")
    parser.add_argument("-d", "--data", default=DATA_FILE, help="Tên file kho lưu trữ tập trung")
    args = parser.parse_args()

    data = load_data(args.data)
    scanned_set = set(data["scanned_ids"])
    saved_playlists = data["meta"].get("playlists", [])
    txt_playlists = read_playlists_txt(PLAYLISTS_TXT)

    input_urls = []
    if args.playlists:
        input_urls = [normalize_playlist_url(u) for u in args.playlists if u.strip()]
    elif txt_playlists:
        input_urls = txt_playlists
    elif saved_playlists:
        input_urls = saved_playlists
    elif sys.stdin.isatty():
        raw = input("🔗 Dán link YouTube Playlist (cách nhau dấu phẩy nếu nhiều link): ").strip()
        if raw:
            input_urls = [normalize_playlist_url(u) for u in raw.split(",") if u.strip()]

    if not input_urls:
        print("⚠️ Chưa có link Playlist nào trong playlists.txt hoặc tham số dòng lệnh.")
        return

    for pl_url in input_urls:
        if pl_url not in saved_playlists:
            saved_playlists.append(pl_url)
    data["meta"]["playlists"] = saved_playlists

    total_new = 0
    total_skipped_unavailable = 0

    for pl_url in input_urls:
        print(f"\n🔍 Đang quét toàn bộ danh sách: {pl_url}")
        pl_title, entries = fetch_all_playlist_entries(pl_url)
        print(f"   📂 Tên Playlist: {pl_title}")
        print(f"   📊 Tổng số mục tìm thấy trên YouTube: {len(entries)}")

        new_in_this_pl = 0
        for idx, entry in enumerate(entries, start=1):
            vid = entry["id"]
            title = (entry.get("title") or "").strip()

            if vid in scanned_set:
                continue

            scanned_set.add(vid)
            data["scanned_ids"].append(vid)

            if title in ("[Deleted video]", "[Private video]", "Deleted video", "Private video"):
                total_skipped_unavailable += 1
                continue

            data["videos"][vid] = {
                "id": vid,
                "index": idx,
                "title": title or f"Video {vid}",
                "channel": entry.get("uploader") or entry.get("channel") or "",
                "duration": entry.get("duration") or 0,
                "youtube_url": f"https://www.youtube.com/watch?v={vid}",
                "status": "unwatched",
                "added_at": now_iso(),
                "subtitles": [],
                "has_vi": False,
            }
            new_in_this_pl += 1
            total_new += 1

        print(f"   ✨ Đã thêm mới: {new_in_this_pl} video.")

    save_data(data, args.data)
    print("\n" + "=" * 52)
    print(f"💾 Đã lưu kho dữ liệu vào: {args.data}")
    print(f"📦 Tổng video hợp lệ trong kho: {len(data['videos'])} video")
    print(f"🆕 Thêm mới trong lượt này:    {total_new} video")
    if total_skipped_unavailable > 0:
        print(f"🚫 Bỏ qua video đã xóa/ẩn:     {total_skipped_unavailable} video")
    print("=" * 52)


if __name__ == "__main__":
    main()
