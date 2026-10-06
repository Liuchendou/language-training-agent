"""Bilibili material source: search English-learning videos on a domestic site.

VOA and BBC are unreachable from some networks (verified on this machine:
connection attempt times out), so the "auto-search material" feature needs a
source that stays reachable. Bilibili's public web API is reachable and exposes
a WBI-signed search endpoint.

The videos this provider returns are ordinary links, so the existing video
import pipeline handles download and transcription unchanged - this module only
answers "which videos are worth importing".
"""

from __future__ import annotations

import hashlib
import html
import http.cookiejar
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass

#: Search keywords per difficulty stage. The user asked for slow English news
#: and stories; VOA's slow-English programmes are widely re-uploaded to
#: Bilibili, so stage 1 targets those, and later stages broaden the pace.
STAGE_KEYWORDS: dict[str, list[str]] = {
    "STAGE_1": ["VOA慢速英语", "慢速英语听力", "英语故事 慢速"],
    "STAGE_2": ["英语听力 中级", "英语新闻 听力"],
    "STAGE_3": ["英语听力 常速", "英语播客 听力"],
}

#: Fixed permutation Bilibili applies to derive the WBI mixin key.
_MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
    27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
    37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
    22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

#: Keyword search returns loosely related uploads; a title must look like
#: English-learning material to be worth offering as a candidate.
_ENGLISH_HINTS = re.compile(
    r"英语|英文|english|listening|听力|慢速|口语|演讲|voa|bbc|ted", re.IGNORECASE
)
#: WBI keys are derived from the nav endpoint; refresh hourly.
_KEY_TTL_SECONDS = 3600


class BilibiliSearchError(RuntimeError):
    """Source cannot be queried; the message carries a readable reason."""


@dataclass
class BilibiliVideo:
    bvid: str
    title: str
    duration_seconds: int
    author: str
    play_count: int
    url: str
    keyword: str = ""

    def as_candidate(self) -> dict[str, object]:
        return {
            "provider": "BILIBILI",
            "provider_item_id": self.bvid,
            "title": self.title,
            "duration_seconds": self.duration_seconds,
            "author": self.author,
            "play_count": self.play_count,
            "url": self.url,
            "matched_keyword": self.keyword,
        }


def _clean_title(raw: str) -> str:
    """Search results wrap matches in <em> tags and HTML-escape the title."""
    text = re.sub(r"<[^>]+>", "", raw)
    # Bilibili mixes named and numeric entities (&#39;, &#x27;, &amp;...), so
    # use the standard decoder rather than a hand-rolled replacement table.
    return html.unescape(text).strip()


def _parse_duration(value: object) -> int:
    """Bilibili returns either seconds (int) or "MM:SS" / "HH:MM:SS" text."""
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return 0
    if ":" not in text:
        try:
            return int(float(text))
        except ValueError:
            return 0
    total = 0
    for part in text.split(":"):
        try:
            total = total * 60 + int(part)
        except ValueError:
            return 0
    return total


class BilibiliMaterialProvider:
    """Query Bilibili's WBI-signed search endpoint for English-learning videos."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout
        self._mixin_key: str | None = None
        self._key_fetched_at = 0.0
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        self._opener.addheaders = [
            ("User-Agent", _USER_AGENT),
            ("Referer", "https://www.bilibili.com"),
        ]

    def _get(self, url: str) -> str:
        with self._opener.open(url, timeout=self.timeout) as response:
            return response.read().decode("utf-8", "ignore")

    def _ensure_mixin_key(self) -> str:
        if self._mixin_key and (time.time() - self._key_fetched_at) < _KEY_TTL_SECONDS:
            return self._mixin_key
        try:
            # Landing on the site first establishes the cookies the API expects.
            self._get("https://www.bilibili.com")
            nav = json.loads(self._get("https://api.bilibili.com/x/web-interface/nav"))
        except Exception as exc:
            raise BilibiliSearchError(
                f"无法连接 B站接口：{type(exc).__name__}: {exc}"
            ) from exc
        wbi = (nav.get("data") or {}).get("wbi_img") or {}
        img_url = str(wbi.get("img_url") or "")
        sub_url = str(wbi.get("sub_url") or "")
        if not img_url or not sub_url:
            raise BilibiliSearchError("B站接口未返回签名密钥（接口可能已变更或触发风控）")
        original = (
            img_url.rsplit("/", 1)[-1].split(".")[0]
            + sub_url.rsplit("/", 1)[-1].split(".")[0]
        )
        self._mixin_key = "".join(original[i] for i in _MIXIN_KEY_ENC_TAB)[:32]
        self._key_fetched_at = time.time()
        return self._mixin_key

    def _sign(self, params: dict[str, object]) -> str:
        mixin_key = self._ensure_mixin_key()
        signed = {**params, "wts": int(time.time())}
        query = urllib.parse.urlencode(sorted((k, str(v)) for k, v in signed.items()))
        signed["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
        return urllib.parse.urlencode(sorted((k, str(v)) for k, v in signed.items()))

    def search(self, keyword: str, *, page: int = 1, page_size: int = 20) -> list[BilibiliVideo]:
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "page_size": page_size,
        }
        url = "https://api.bilibili.com/x/web-interface/wbi/search/type?" + self._sign(params)
        try:
            payload = json.loads(self._get(url))
        except BilibiliSearchError:
            raise
        except Exception as exc:
            raise BilibiliSearchError(
                f"B站搜索请求失败：{type(exc).__name__}: {exc}"
            ) from exc
        code = payload.get("code")
        if code != 0:
            raise BilibiliSearchError(
                f"B站搜索返回错误 {code}：{payload.get('message') or '未知错误'}"
            )
        results = (payload.get("data") or {}).get("result") or []
        videos: list[BilibiliVideo] = []
        for item in results:
            bvid = str(item.get("bvid") or "").strip()
            title = _clean_title(str(item.get("title") or ""))
            if not bvid or not title:
                continue
            try:
                play = int(item.get("play") or 0)
            except (TypeError, ValueError):
                play = 0
            videos.append(
                BilibiliVideo(
                    bvid=bvid,
                    title=title,
                    duration_seconds=_parse_duration(item.get("duration")),
                    author=str(item.get("author") or "").strip(),
                    play_count=play,
                    url=f"https://www.bilibili.com/video/{bvid}",
                    keyword=keyword,
                )
            )
        return videos

    def search_candidates(
        self,
        keywords: list[str],
        *,
        duration_min_seconds: int = 300,
        duration_max_seconds: int = 1800,
        limit: int = 12,
        errors: list[str] | None = None,
    ) -> list[BilibiliVideo]:
        """Merge several keyword searches into one ranked, de-duplicated list.

        A keyword that fails does not hide the others: the reason is collected
        so an unreachable source stays distinguishable from "nothing matched".
        """
        seen: set[str] = set()
        merged: list[BilibiliVideo] = []
        for keyword in keywords:
            try:
                found = self.search(keyword)
            except BilibiliSearchError as exc:
                if errors is not None:
                    errors.append(f"关键词「{keyword}」：{exc}")
                continue
            for video in found:
                if video.bvid in seen:
                    continue
                if not _ENGLISH_HINTS.search(video.title):
                    continue
                if not duration_min_seconds <= video.duration_seconds <= duration_max_seconds:
                    continue
                seen.add(video.bvid)
                merged.append(video)
        # Prefer the more-watched uploads; they are likelier to have clean audio.
        merged.sort(key=lambda item: item.play_count, reverse=True)
        return merged[:limit]
