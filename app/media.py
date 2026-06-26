"""Single-media download dispatch.

Given one instagrapi `media` object, download it to `folder` using the right
helper for its type (photo / album / video / clip / igtv) and return the list
of saved file paths.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger("ig")

# instagrapi media_type values
PHOTO = 1
VIDEO = 2
ALBUM = 8


def download_one(cl, media, folder):
    """Download a single media object using its already fetched details.

    Avoids calling cl.media_info(pk) which performs slow GQL lookup queries.
    """
    mt = getattr(media, "media_type", None)
    pk = media.pk
    username = getattr(getattr(media, "user", None), "username", "") or "unknown"
    folder = Path(folder)

    # Helper to clean/check returned paths
    def _path_list(p):
        return [str(p)] if p else []

    if mt == PHOTO:
        filename = f"{pk}"
        url = getattr(media, "thumbnail_url", None)
        if not url:
            iv = getattr(media, "image_versions2", None) or {}
            candidates = iv.get("candidates", [])
            if candidates:
                url = candidates[0].get("url")
        if not url:
            return _path_list(cl.photo_download(pk, folder=folder))
        return _path_list(cl.photo_download_by_url(url, filename, folder))

    if mt == ALBUM:
        resources = getattr(media, "resources", [])
        if not resources:
            return [str(p) for p in cl.album_download(pk, folder=folder) if p]
        paths = []
        for resource in resources:
            res_pk = resource.pk
            res_mt = resource.media_type
            filename = f"{res_pk}"
            if res_mt == PHOTO:
                url = getattr(resource, "thumbnail_url", None)
                if not url:
                    iv = getattr(resource, "image_versions2", None) or {}
                    candidates = iv.get("candidates", [])
                    if candidates:
                        url = candidates[0].get("url")
                if url:
                    p = cl.photo_download_by_url(url, filename, folder)
                    if p:
                        paths.append(str(p))
            elif res_mt == VIDEO:
                url = getattr(resource, "video_url", None)
                if not url:
                    vv = getattr(resource, "video_versions", None) or []
                    if vv:
                        url = vv[0].get("url")
                if url:
                    p = cl.video_download_by_url(url, filename, folder)
                    if p:
                        paths.append(str(p))
        return paths

    if mt == VIDEO:
        filename = f"{pk}"
        url = getattr(media, "video_url", None)
        if not url:
            vv = getattr(media, "video_versions", None) or []
            if vv:
                url = vv[0].get("url")
        if not url:
            return _path_list(cl.video_download(pk, folder=folder))
        return _path_list(cl.video_download_by_url(url, filename, folder))

    # Unknown type: try to download best-effort.
    log.warning(f"unknown media_type={mt!r} for pk={pk}; trying direct standard photo/video fallback")
    try:
        if getattr(media, "video_url", None):
            return _path_list(cl.video_download(pk, folder=folder))
        return _path_list(cl.photo_download(pk, folder=folder))
    except Exception as e:
        log.warning(f"fallback download failed: {e}")
        return []
