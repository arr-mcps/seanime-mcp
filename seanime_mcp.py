"""MCP tools for the Seanime REST API.

Full API coverage, exposed as 9 resource-scoped *portmanteau* tools instead
of one tool per endpoint. Each tool takes an `operation` enum plus an
`arguments` dict; see AGENTS.md for the rationale (a 200+-tool server blows
the MCP context budget on session start). `_GROUPS` near the bottom buckets
every endpoint function by resource and `_register_group` wraps each bucket
in one dispatching MCP tool; the functions themselves are not tools anymore.

Auth: requests carry `X-Seanime-Token`, which is the SHA256 hex of the
server password (see `internal/core/app.go` upstream: `ServerPasswordHash`).
Set `SEANIME_API_KEY` to that token value. Request bodies stay plain JSON
dictionaries matching the running version's DTOs.

Binary/streaming endpoints (mediastream/directstream/proxy/nakama streams,
websocket events, image proxy) are intentionally not exposed: they return
media bytes or never-ending streams, not JSON. Server self-update and
local-machine side effects (open-in-explorer, start media player,
install-update) are excluded as well.
"""

import inspect
import os
import sys
from typing import Any, Literal
from urllib.parse import quote

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

JSONObj = dict[str, Any]
JSONVal = JSONObj | list[Any]
ReturnVal = JSONVal | str | int | float | bool | None
READONLY = ToolAnnotations(readOnlyHint=True)

mcp = FastMCP("seanime-mcp")
_client: httpx.AsyncClient | None = None


def build_client(
    base_url: str,
    api_key: str | None,
    transport: httpx.BaseTransport | None = None,
) -> httpx.AsyncClient:
    headers = {"X-Seanime-Token": api_key} if api_key else {}
    return httpx.AsyncClient(
        base_url=f"{base_url.rstrip('/')}/api/v1",
        headers=headers,
        transport=transport,
    )


def _path(value: Any) -> str:
    return quote(str(value), safe="")


def _params(**values: Any) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None}


def _decode_response(response: httpx.Response) -> ReturnVal:
    """Parse a successful response as JSON, a JSON scalar, or raw text."""
    import json

    if not response.content:
        return {}
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        return response.json()
    text = response.text
    try:
        return json.loads(text)
    except ValueError:
        return text


async def _req(
    method: str,
    path: str,
    json: Any = None,
    params: dict[str, Any] | None = None,
) -> ReturnVal:
    assert _client is not None, "client not configured"
    response = await _client.request(method, path, json=json, params=params)
    if response.status_code >= 400:
        try:
            body = response.json()
            message = body.get("message", body) if isinstance(body, dict) else body
        except ValueError:
            message = response.text
        raise ToolError(f"Seanime API {response.status_code}: {message}")
    return _decode_response(response)


# system ---------------------------------------------------------------------

async def seanime_get_status() -> ReturnVal:
    """Get server status (GET /api/v1/status)."""
    return await _req("GET", "/status")


async def seanime_get_home_items() -> ReturnVal:
    """Get home screen items (GET /api/v1/status/home-items)."""
    return await _req("GET", "/status/home-items")


async def seanime_update_home_items(payload: dict) -> ReturnVal:
    """Update home screen items (POST /api/v1/status/home-items)."""
    return await _req("POST", "/status/home-items", json=payload)


async def seanime_get_announcements(payload: dict) -> ReturnVal:
    """Get announcements for a platform (POST /api/v1/announcements)."""
    return await _req("POST", "/announcements", json=payload)


async def seanime_get_latest_update() -> ReturnVal:
    """Get latest release info (GET /api/v1/latest-update)."""
    return await _req("GET", "/latest-update")


async def seanime_get_changelog(after: str = None, before: str = None) -> ReturnVal:
    """Get changelog entries (GET /api/v1/changelog)."""
    return await _req("GET", "/changelog", params=_params(after=after, before=before))


async def seanime_check_for_updates() -> ReturnVal:
    """Check for updates (POST /api/v1/check-for-updates)."""
    return await _req("POST", "/check-for-updates")


async def seanime_get_log_filenames() -> ReturnVal:
    """List log files (GET /api/v1/logs/filenames)."""
    return await _req("GET", "/logs/filenames")


async def seanime_get_latest_log() -> ReturnVal:
    """Get latest log content (GET /api/v1/logs/latest)."""
    return await _req("GET", "/logs/latest")


async def seanime_get_log_content(path: str) -> ReturnVal:
    """Get log file content (GET /api/v1/log/*path)."""
    return await _req("GET", f"/log/{_path(path)}")


async def seanime_delete_logs() -> ReturnVal:
    """Delete logs (DELETE /api/v1/logs)."""
    return await _req("DELETE", "/logs")


async def seanime_get_memory_stats() -> ReturnVal:
    """Get memory stats (GET /api/v1/memory/stats)."""
    return await _req("GET", "/memory/stats")


async def seanime_get_theme() -> ReturnVal:
    """Get UI theme (GET /api/v1/theme)."""
    return await _req("GET", "/theme")


async def seanime_get_docs() -> ReturnVal:
    """Get internal API docs (GET /api/v1/internal/docs)."""
    return await _req("GET", "/internal/docs")


# library --------------------------------------------------------------------

async def seanime_get_local_files() -> ReturnVal:
    """List scanned local files (GET /api/v1/library/local-files)."""
    return await _req("GET", "/library/local-files")


async def seanime_local_file_bulk_action(payload: dict) -> ReturnVal:
    """Bulk action on local files (POST /api/v1/library/local-files)."""
    return await _req("POST", "/library/local-files", json=payload)


async def seanime_update_local_files(payload: dict) -> ReturnVal:
    """Update local files (PATCH /api/v1/library/local-files)."""
    return await _req("PATCH", "/library/local-files", json=payload)


async def seanime_delete_local_files(payload: dict) -> ReturnVal:
    """Delete local files entries (DELETE /api/v1/library/local-files)."""
    return await _req("DELETE", "/library/local-files", json=payload)


async def seanime_update_local_file_data(payload: dict) -> ReturnVal:
    """Update a single local file's data (PATCH /api/v1/library/local-file)."""
    return await _req("PATCH", "/library/local-file", json=payload)


async def seanime_super_update_local_files(payload: dict) -> ReturnVal:
    """Super-update local files (PATCH /api/v1/library/local-files/super-update)."""
    return await _req("PATCH", "/library/local-files/super-update", json=payload)


async def seanime_dump_local_files() -> ReturnVal:
    """Dump local files to file (GET /api/v1/library/local-files/dump)."""
    return await _req("GET", "/library/local-files/dump")


async def seanime_import_local_files(payload: dict) -> ReturnVal:
    """Import local files (POST /api/v1/library/local-files/import)."""
    return await _req("POST", "/library/local-files/import", json=payload)


async def seanime_get_library_collection() -> ReturnVal:
    """Get library collection (AniList collection matched with local files) (GET /api/v1/library/collection)."""
    return await _req("GET", "/library/collection")


async def seanime_get_schedule() -> ReturnVal:
    """Get airing schedule (GET /api/v1/library/schedule)."""
    return await _req("GET", "/library/schedule")


async def seanime_get_scan_summaries() -> ReturnVal:
    """Get scan summaries (GET /api/v1/library/scan-summaries)."""
    return await _req("GET", "/library/scan-summaries")


async def seanime_get_missing_episodes() -> ReturnVal:
    """Get missing episodes (GET /api/v1/library/missing-episodes)."""
    return await _req("GET", "/library/missing-episodes")


async def seanime_get_upcoming_episodes() -> ReturnVal:
    """Get upcoming episodes (GET /api/v1/library/upcoming-episodes)."""
    return await _req("GET", "/library/upcoming-episodes")


async def seanime_scan(payload: dict) -> ReturnVal:
    """Scan local library (POST /api/v1/library/scan)."""
    return await _req("POST", "/library/scan", json=payload)


async def seanime_remove_empty_directories() -> ReturnVal:
    """Remove empty library directories (DELETE /api/v1/library/empty-directories)."""
    return await _req("DELETE", "/library/empty-directories")


async def seanime_get_anime_entry(id: int) -> ReturnVal:
    """Get anime library entry (GET /api/v1/library/anime-entry/{id})."""
    return await _req("GET", f"/library/anime-entry/{_path(id)}")


async def seanime_fetch_entry_suggestions(payload: dict) -> ReturnVal:
    """Fetch match suggestions for an entry (POST /api/v1/library/anime-entry/suggestions)."""
    return await _req("POST", "/library/anime-entry/suggestions", json=payload)


async def seanime_manual_match(payload: dict) -> ReturnVal:
    """Manually match an entry (POST /api/v1/library/anime-entry/manual-match)."""
    return await _req("POST", "/library/anime-entry/manual-match", json=payload)


async def seanime_entry_bulk_action(payload: dict) -> ReturnVal:
    """Bulk action on anime entries (PATCH /api/v1/library/anime-entry/bulk-action)."""
    return await _req("PATCH", "/library/anime-entry/bulk-action", json=payload)


async def seanime_update_entry_progress(payload: dict) -> ReturnVal:
    """Update entry progress (POST /api/v1/library/anime-entry/update-progress)."""
    return await _req("POST", "/library/anime-entry/update-progress", json=payload)


async def seanime_update_entry_repeat(payload: dict) -> ReturnVal:
    """Update entry repeat count (POST /api/v1/library/anime-entry/update-repeat)."""
    return await _req("POST", "/library/anime-entry/update-repeat", json=payload)


async def seanime_get_silence_status(id: int) -> ReturnVal:
    """Get entry silence status (GET /api/v1/library/anime-entry/silence/{id})."""
    return await _req("GET", f"/library/anime-entry/silence/{_path(id)}")


async def seanime_toggle_silence(payload: dict) -> ReturnVal:
    """Toggle entry silence status (POST /api/v1/library/anime-entry/silence)."""
    return await _req("POST", "/library/anime-entry/silence", json=payload)


async def seanime_add_unknown_media(payload: dict) -> ReturnVal:
    """Add unknown media (POST /api/v1/library/unknown-media)."""
    return await _req("POST", "/library/unknown-media", json=payload)


async def seanime_get_episode_collection(id: int) -> ReturnVal:
    """Get episode collection for media (GET /api/v1/anime/episode-collection/{id})."""
    return await _req("GET", f"/anime/episode-collection/{_path(id)}")


async def seanime_get_file_tree() -> ReturnVal:
    """Get library explorer file tree (GET /api/v1/library/explorer/file-tree)."""
    return await _req("GET", "/library/explorer/file-tree")


async def seanime_refresh_file_tree() -> ReturnVal:
    """Refresh library explorer file tree (POST /api/v1/library/explorer/file-tree/refresh)."""
    return await _req("POST", "/library/explorer/file-tree/refresh")


async def seanime_load_directory_children(payload: dict) -> ReturnVal:
    """Load explorer directory children (POST /api/v1/library/explorer/directory-children)."""
    return await _req("POST", "/library/explorer/directory-children", json=payload)


async def seanime_populate_filler(payload: dict) -> ReturnVal:
    """Populate filler metadata (POST /api/v1/metadata-provider/filler)."""
    return await _req("POST", "/metadata-provider/filler", json=payload)


async def seanime_remove_filler(payload: dict) -> ReturnVal:
    """Remove filler metadata (DELETE /api/v1/metadata-provider/filler)."""
    return await _req("DELETE", "/metadata-provider/filler", json=payload)


async def seanime_get_metadata_parent(id: int) -> ReturnVal:
    """Get media metadata parent (GET /api/v1/metadata/parent/{id})."""
    return await _req("GET", f"/metadata/parent/{_path(id)}")


async def seanime_save_metadata_parent(payload: dict) -> ReturnVal:
    """Save media metadata parent (POST /api/v1/metadata/parent)."""
    return await _req("POST", "/metadata/parent", json=payload)


async def seanime_delete_metadata_parent(payload: dict) -> ReturnVal:
    """Delete media metadata parent (DELETE /api/v1/metadata/parent)."""
    return await _req("DELETE", "/metadata/parent", json=payload)


# anilist --------------------------------------------------------------------

async def seanime_get_anilist_collection() -> ReturnVal:
    """Get AniList anime collection (GET /api/v1/anilist/collection)."""
    return await _req("GET", "/anilist/collection")


async def seanime_refresh_anilist_collection() -> ReturnVal:
    """Refresh AniList anime collection (POST /api/v1/anilist/collection)."""
    return await _req("POST", "/anilist/collection")


async def seanime_get_raw_anilist_collection() -> ReturnVal:
    """Get raw AniList anime collection (GET /api/v1/anilist/collection/raw)."""
    return await _req("GET", "/anilist/collection/raw")


async def seanime_get_raw_collection_tags() -> ReturnVal:
    """Get raw collection tags (GET /api/v1/anilist/collection/raw/tags)."""
    return await _req("GET", "/anilist/collection/raw/tags")


async def seanime_get_media_details(id: int) -> ReturnVal:
    """Get AniList anime details (GET /api/v1/anilist/media-details/{id})."""
    return await _req("GET", f"/anilist/media-details/{_path(id)}")


async def seanime_get_studio_details(id: int) -> ReturnVal:
    """Get AniList studio details (GET /api/v1/anilist/studio-details/{id})."""
    return await _req("GET", f"/anilist/studio-details/{_path(id)}")


async def seanime_edit_list_entry(payload: dict) -> ReturnVal:
    """Edit AniList list entry (POST /api/v1/anilist/list-entry)."""
    return await _req("POST", "/anilist/list-entry", json=payload)


async def seanime_delete_list_entry(payload: dict) -> ReturnVal:
    """Delete AniList list entry (DELETE /api/v1/anilist/list-entry)."""
    return await _req("DELETE", "/anilist/list-entry", json=payload)


async def seanime_list_anime(payload: dict) -> ReturnVal:
    """Browse AniList anime (POST /api/v1/anilist/list-anime)."""
    return await _req("POST", "/anilist/list-anime", json=payload)


async def seanime_list_recent_anime(payload: dict) -> ReturnVal:
    """List recently airing anime (POST /api/v1/anilist/list-recent-anime)."""
    return await _req("POST", "/anilist/list-recent-anime", json=payload)


async def seanime_list_missed_sequels() -> ReturnVal:
    """List missed sequels (GET /api/v1/anilist/list-missed-sequels)."""
    return await _req("GET", "/anilist/list-missed-sequels")


async def seanime_get_anilist_stats() -> ReturnVal:
    """Get AniList stats (GET /api/v1/anilist/stats)."""
    return await _req("GET", "/anilist/stats")


async def seanime_get_cache_status() -> ReturnVal:
    """Get AniList cache layer status (GET /api/v1/anilist/cache-layer/status)."""
    return await _req("GET", "/anilist/cache-layer/status")


async def seanime_toggle_cache() -> ReturnVal:
    """Toggle AniList cache layer status (POST /api/v1/anilist/cache-layer/status)."""
    return await _req("POST", "/anilist/cache-layer/status")


# torrent --------------------------------------------------------------------

async def seanime_search_torrent(payload: dict) -> ReturnVal:
    """Search torrents via providers (POST /api/v1/torrent/search)."""
    return await _req("POST", "/torrent/search", json=payload)


async def seanime_client_download(payload: dict) -> ReturnVal:
    """Download via torrent client (POST /api/v1/torrent-client/download)."""
    return await _req("POST", "/torrent-client/download", json=payload)


async def seanime_client_list(category: str = None, sort: str = None) -> ReturnVal:
    """List active torrents (GET /api/v1/torrent-client/list)."""
    return await _req("GET", "/torrent-client/list", params=_params(category=category, sort=sort))


async def seanime_client_details(hash: str) -> ReturnVal:
    """Get built-in torrent client details (GET /api/v1/torrent-client/details)."""
    return await _req("GET", "/torrent-client/details", params=_params(hash=hash))


async def seanime_client_action(payload: dict) -> ReturnVal:
    """Torrent client action (POST /api/v1/torrent-client/action)."""
    return await _req("POST", "/torrent-client/action", json=payload)


async def seanime_client_get_files(payload: dict) -> ReturnVal:
    """Get torrent client files (POST /api/v1/torrent-client/get-files)."""
    return await _req("POST", "/torrent-client/get-files", json=payload)


async def seanime_client_rule_magnet(payload: dict) -> ReturnVal:
    """Add magnet from auto-downloader rule (POST /api/v1/torrent-client/rule-magnet)."""
    return await _req("POST", "/torrent-client/rule-magnet", json=payload)


async def seanime_autodl_run() -> ReturnVal:
    """Run auto-downloader (POST /api/v1/auto-downloader/run)."""
    return await _req("POST", "/auto-downloader/run")


async def seanime_autodl_run_simulation() -> ReturnVal:
    """Run auto-downloader simulation (POST /api/v1/auto-downloader/run/simulation)."""
    return await _req("POST", "/auto-downloader/run/simulation")


async def seanime_get_autodl_rule(id: str) -> ReturnVal:
    """Get auto-downloader rule (GET /api/v1/auto-downloader/rule/{id})."""
    return await _req("GET", f"/auto-downloader/rule/{_path(id)}")


async def seanime_get_autodl_rules_by_anime(id: int) -> ReturnVal:
    """Get auto-downloader rules by anime (GET /api/v1/auto-downloader/rule/anime/{id})."""
    return await _req("GET", f"/auto-downloader/rule/anime/{_path(id)}")


async def seanime_get_autodl_rules() -> ReturnVal:
    """List auto-downloader rules (GET /api/v1/auto-downloader/rules)."""
    return await _req("GET", "/auto-downloader/rules")


async def seanime_create_autodl_rule(payload: dict) -> ReturnVal:
    """Create auto-downloader rule (POST /api/v1/auto-downloader/rule)."""
    return await _req("POST", "/auto-downloader/rule", json=payload)


async def seanime_update_autodl_rule(payload: dict) -> ReturnVal:
    """Update auto-downloader rule (PATCH /api/v1/auto-downloader/rule)."""
    return await _req("PATCH", "/auto-downloader/rule", json=payload)


async def seanime_delete_autodl_rule(id: str) -> ReturnVal:
    """Delete auto-downloader rule (DELETE /api/v1/auto-downloader/rule/{id})."""
    return await _req("DELETE", f"/auto-downloader/rule/{_path(id)}")


async def seanime_get_autodl_items() -> ReturnVal:
    """Get auto-downloader items (GET /api/v1/auto-downloader/items)."""
    return await _req("GET", "/auto-downloader/items")


async def seanime_delete_autodl_item(payload: dict) -> ReturnVal:
    """Delete auto-downloader item (DELETE /api/v1/auto-downloader/item)."""
    return await _req("DELETE", "/auto-downloader/item", json=payload)


async def seanime_get_autodl_profiles() -> ReturnVal:
    """List auto-downloader profiles (GET /api/v1/auto-downloader/profiles)."""
    return await _req("GET", "/auto-downloader/profiles")


async def seanime_get_autodl_profile(id: str) -> ReturnVal:
    """Get auto-downloader profile (GET /api/v1/auto-downloader/profile/{id})."""
    return await _req("GET", f"/auto-downloader/profile/{_path(id)}")


async def seanime_create_autodl_profile(payload: dict) -> ReturnVal:
    """Create auto-downloader profile (POST /api/v1/auto-downloader/profile)."""
    return await _req("POST", "/auto-downloader/profile", json=payload)


async def seanime_update_autodl_profile(payload: dict) -> ReturnVal:
    """Update auto-downloader profile (PATCH /api/v1/auto-downloader/profile)."""
    return await _req("PATCH", "/auto-downloader/profile", json=payload)


async def seanime_delete_autodl_profile(id: str) -> ReturnVal:
    """Delete auto-downloader profile (DELETE /api/v1/auto-downloader/profile/{id})."""
    return await _req("DELETE", f"/auto-downloader/profile/{_path(id)}")


async def seanime_get_autoselect_profile() -> ReturnVal:
    """Get auto-select profile (GET /api/v1/auto-select/profile)."""
    return await _req("GET", "/auto-select/profile")


async def seanime_save_autoselect_profile(payload: dict) -> ReturnVal:
    """Save auto-select profile (POST /api/v1/auto-select/profile)."""
    return await _req("POST", "/auto-select/profile", json=payload)


async def seanime_delete_autoselect_profile() -> ReturnVal:
    """Delete auto-select profile (DELETE /api/v1/auto-select/profile)."""
    return await _req("DELETE", "/auto-select/profile")


async def seanime_debrid_get_torrents() -> ReturnVal:
    """Get debrid torrents (GET /api/v1/debrid/torrents)."""
    return await _req("GET", "/debrid/torrents")


async def seanime_debrid_add_torrents(payload: dict) -> ReturnVal:
    """Add debrid torrents (POST /api/v1/debrid/torrents)."""
    return await _req("POST", "/debrid/torrents", json=payload)


async def seanime_debrid_download(payload: dict) -> ReturnVal:
    """Download debrid torrent (POST /api/v1/debrid/torrents/download)."""
    return await _req("POST", "/debrid/torrents/download", json=payload)


async def seanime_debrid_cancel_download(payload: dict) -> ReturnVal:
    """Cancel debrid download (POST /api/v1/debrid/torrents/cancel)."""
    return await _req("POST", "/debrid/torrents/cancel", json=payload)


async def seanime_debrid_delete_torrent(payload: dict) -> ReturnVal:
    """Delete debrid torrent (DELETE /api/v1/debrid/torrent)."""
    return await _req("DELETE", "/debrid/torrent", json=payload)


async def seanime_debrid_torrent_info(payload: dict) -> ReturnVal:
    """Get debrid torrent info (POST /api/v1/debrid/torrents/info)."""
    return await _req("POST", "/debrid/torrents/info", json=payload)


async def seanime_debrid_file_previews(payload: dict) -> ReturnVal:
    """Get debrid torrent file previews (POST /api/v1/debrid/torrents/file-previews)."""
    return await _req("POST", "/debrid/torrents/file-previews", json=payload)


async def seanime_debrid_start_stream(payload: dict) -> ReturnVal:
    """Start debrid stream (POST /api/v1/debrid/stream/start)."""
    return await _req("POST", "/debrid/stream/start", json=payload)


async def seanime_debrid_cancel_stream(payload: dict) -> ReturnVal:
    """Cancel debrid stream (POST /api/v1/debrid/stream/cancel)."""
    return await _req("POST", "/debrid/stream/cancel", json=payload)


# manga ----------------------------------------------------------------------

async def seanime_manga_anilist_collection(payload: dict) -> ReturnVal:
    """Get AniList manga collection (POST /api/v1/manga/anilist/collection)."""
    return await _req("POST", "/manga/anilist/collection", json=payload)


async def seanime_manga_anilist_raw() -> ReturnVal:
    """Get raw AniList manga collection (GET /api/v1/manga/anilist/collection/raw)."""
    return await _req("GET", "/manga/anilist/collection/raw")


async def seanime_manga_anilist_raw_tags() -> ReturnVal:
    """Get raw manga collection tags (GET /api/v1/manga/anilist/collection/raw/tags)."""
    return await _req("GET", "/manga/anilist/collection/raw/tags")


async def seanime_manga_anilist_list(payload: dict) -> ReturnVal:
    """Browse AniList manga (POST /api/v1/manga/anilist/list)."""
    return await _req("POST", "/manga/anilist/list", json=payload)


async def seanime_manga_get_collection() -> ReturnVal:
    """Get manga collection (GET /api/v1/manga/collection)."""
    return await _req("GET", "/manga/collection")


async def seanime_manga_get_preferences() -> ReturnVal:
    """Get manga preferences (GET /api/v1/manga/preferences)."""
    return await _req("GET", "/manga/preferences")


async def seanime_manga_import_preferences(payload: dict) -> ReturnVal:
    """Import manga preferences (POST /api/v1/manga/preferences/import)."""
    return await _req("POST", "/manga/preferences/import", json=payload)


async def seanime_manga_patch_preference(media_id: int, payload: dict) -> ReturnVal:
    """Patch manga preference (PATCH /api/v1/manga/preferences/{mediaId})."""
    return await _req("PATCH", f"/manga/preferences/{_path(media_id)}", json=payload)


async def seanime_manga_start_source_refresh(payload: dict) -> ReturnVal:
    """Start manga source refresh (POST /api/v1/manga/source-refresh)."""
    return await _req("POST", "/manga/source-refresh", json=payload)


async def seanime_manga_get_source_refresh() -> ReturnVal:
    """Get manga source refresh status (GET /api/v1/manga/source-refresh)."""
    return await _req("GET", "/manga/source-refresh")


async def seanime_manga_stop_source_refresh() -> ReturnVal:
    """Stop manga source refresh (DELETE /api/v1/manga/source-refresh)."""
    return await _req("DELETE", "/manga/source-refresh")


async def seanime_manga_latest_chapter_numbers() -> ReturnVal:
    """Get latest chapter numbers map (GET /api/v1/manga/latest-chapter-numbers)."""
    return await _req("GET", "/manga/latest-chapter-numbers")


async def seanime_manga_refetch_chapters(payload: dict) -> ReturnVal:
    """Refetch manga chapter containers (POST /api/v1/manga/refetch-chapter-containers)."""
    return await _req("POST", "/manga/refetch-chapter-containers", json=payload)


async def seanime_manga_get_entry(id: int) -> ReturnVal:
    """Get manga entry (GET /api/v1/manga/entry/{id})."""
    return await _req("GET", f"/manga/entry/{_path(id)}")


async def seanime_manga_get_entry_details(id: int) -> ReturnVal:
    """Get manga entry details (GET /api/v1/manga/entry/{id}/details)."""
    return await _req("GET", f"/manga/entry/{_path(id)}/details")


async def seanime_manga_empty_entry_cache(payload: dict) -> ReturnVal:
    """Empty manga entry cache (DELETE /api/v1/manga/entry/cache)."""
    return await _req("DELETE", "/manga/entry/cache", json=payload)


async def seanime_manga_get_chapters(payload: dict) -> ReturnVal:
    """Get manga entry chapters (POST /api/v1/manga/chapters)."""
    return await _req("POST", "/manga/chapters", json=payload)


async def seanime_manga_get_pages(payload: dict) -> ReturnVal:
    """Get manga entry pages (POST /api/v1/manga/pages)."""
    return await _req("POST", "/manga/pages", json=payload)


async def seanime_manga_update_progress(payload: dict) -> ReturnVal:
    """Update manga progress (POST /api/v1/manga/update-progress)."""
    return await _req("POST", "/manga/update-progress", json=payload)


async def seanime_manga_get_downloaded_chapters(id: int) -> ReturnVal:
    """Get downloaded chapters (GET /api/v1/manga/downloaded-chapters/{id})."""
    return await _req("GET", f"/manga/downloaded-chapters/{_path(id)}")


async def seanime_manga_get_downloads() -> ReturnVal:
    """Get manga downloads list (GET /api/v1/manga/downloads)."""
    return await _req("GET", "/manga/downloads")


async def seanime_manga_download_chapters(payload: dict) -> ReturnVal:
    """Download manga chapters (POST /api/v1/manga/download-chapters)."""
    return await _req("POST", "/manga/download-chapters", json=payload)


async def seanime_manga_get_download_data(payload: dict) -> ReturnVal:
    """Get manga download data (POST /api/v1/manga/download-data)."""
    return await _req("POST", "/manga/download-data", json=payload)


async def seanime_manga_delete_downloaded_chapters(payload: dict) -> ReturnVal:
    """Delete downloaded chapters (DELETE /api/v1/manga/download-chapter)."""
    return await _req("DELETE", "/manga/download-chapter", json=payload)


async def seanime_manga_get_download_queue() -> ReturnVal:
    """Get manga download queue (GET /api/v1/manga/download-queue)."""
    return await _req("GET", "/manga/download-queue")


async def seanime_manga_start_download_queue() -> ReturnVal:
    """Start manga download queue (POST /api/v1/manga/download-queue/start)."""
    return await _req("POST", "/manga/download-queue/start")


async def seanime_manga_stop_download_queue() -> ReturnVal:
    """Stop manga download queue (POST /api/v1/manga/download-queue/stop)."""
    return await _req("POST", "/manga/download-queue/stop")


async def seanime_manga_clear_download_queue() -> ReturnVal:
    """Clear chapter download queue (DELETE /api/v1/manga/download-queue)."""
    return await _req("DELETE", "/manga/download-queue")


async def seanime_manga_reset_errored_queue() -> ReturnVal:
    """Reset errored chapter downloads (POST /api/v1/manga/download-queue/reset-errored)."""
    return await _req("POST", "/manga/download-queue/reset-errored")


async def seanime_manga_manual_search(payload: dict) -> ReturnVal:
    """Manual manga search (POST /api/v1/manga/search)."""
    return await _req("POST", "/manga/search", json=payload)


async def seanime_manga_preview_mapping(payload: dict) -> ReturnVal:
    """Preview manga mapping (POST /api/v1/manga/manual-mapping/preview)."""
    return await _req("POST", "/manga/manual-mapping/preview", json=payload)


async def seanime_manga_manual_mapping(payload: dict) -> ReturnVal:
    """Manual manga mapping (POST /api/v1/manga/manual-mapping)."""
    return await _req("POST", "/manga/manual-mapping", json=payload)


async def seanime_manga_get_mapping(payload: dict) -> ReturnVal:
    """Get manga mapping (POST /api/v1/manga/get-mapping)."""
    return await _req("POST", "/manga/get-mapping", json=payload)


async def seanime_manga_remove_mapping(payload: dict) -> ReturnVal:
    """Remove manga mapping (POST /api/v1/manga/remove-mapping)."""
    return await _req("POST", "/manga/remove-mapping", json=payload)


# playback -------------------------------------------------------------------

async def seanime_playback_sync_progress(payload: dict) -> ReturnVal:
    """Sync current playback progress (POST /api/v1/playback-manager/sync-current-progress)."""
    return await _req("POST", "/playback-manager/sync-current-progress", json=payload)


async def seanime_playback_start_playlist(payload: dict) -> ReturnVal:
    """Start playback playlist (POST /api/v1/playback-manager/start-playlist)."""
    return await _req("POST", "/playback-manager/start-playlist", json=payload)


async def seanime_playback_playlist_next() -> ReturnVal:
    """Play next playlist item (POST /api/v1/playback-manager/playlist-next)."""
    return await _req("POST", "/playback-manager/playlist-next")


async def seanime_playback_cancel_playlist() -> ReturnVal:
    """Cancel current playlist (POST /api/v1/playback-manager/cancel-playlist)."""
    return await _req("POST", "/playback-manager/cancel-playlist")


async def seanime_playback_play_next_episode(payload: dict) -> ReturnVal:
    """Play next episode (POST /api/v1/playback-manager/next-episode)."""
    return await _req("POST", "/playback-manager/next-episode", json=payload)


async def seanime_playback_get_next_episode() -> ReturnVal:
    """Get next episode (GET /api/v1/playback-manager/next-episode)."""
    return await _req("GET", "/playback-manager/next-episode")


async def seanime_playback_autoplay_next(payload: dict) -> ReturnVal:
    """Autoplay next episode (POST /api/v1/playback-manager/autoplay-next-episode)."""
    return await _req("POST", "/playback-manager/autoplay-next-episode", json=payload)


async def seanime_playback_play(payload: dict) -> ReturnVal:
    """Play video (POST /api/v1/playback-manager/play)."""
    return await _req("POST", "/playback-manager/play", json=payload)


async def seanime_playback_play_random(payload: dict) -> ReturnVal:
    """Play random video (POST /api/v1/playback-manager/play-random)."""
    return await _req("POST", "/playback-manager/play-random", json=payload)


async def seanime_playback_start_manual_tracking(payload: dict) -> ReturnVal:
    """Start manual tracking (POST /api/v1/playback-manager/manual-tracking/start)."""
    return await _req("POST", "/playback-manager/manual-tracking/start", json=payload)


async def seanime_playback_cancel_manual_tracking() -> ReturnVal:
    """Cancel manual tracking (POST /api/v1/playback-manager/manual-tracking/cancel)."""
    return await _req("POST", "/playback-manager/manual-tracking/cancel")


async def seanime_get_playlists() -> ReturnVal:
    """List playlists (GET /api/v1/playlists)."""
    return await _req("GET", "/playlists")


async def seanime_create_playlist(payload: dict) -> ReturnVal:
    """Create playlist (POST /api/v1/playlist)."""
    return await _req("POST", "/playlist", json=payload)


async def seanime_update_playlist(payload: dict) -> ReturnVal:
    """Update playlist (PATCH /api/v1/playlist)."""
    return await _req("PATCH", "/playlist", json=payload)


async def seanime_delete_playlist(payload: dict) -> ReturnVal:
    """Delete playlist (DELETE /api/v1/playlist)."""
    return await _req("DELETE", "/playlist", json=payload)


async def seanime_get_playlist_episodes(id: str) -> ReturnVal:
    """Get playlist episodes (GET /api/v1/playlist/episodes/{id})."""
    return await _req("GET", f"/playlist/episodes/{_path(id)}")


async def seanime_stream_get_episode_source(payload: dict) -> ReturnVal:
    """Get online-stream episode source (POST /api/v1/onlinestream/episode-source)."""
    return await _req("POST", "/onlinestream/episode-source", json=payload)


async def seanime_stream_get_episode_list(payload: dict) -> ReturnVal:
    """Get online-stream episode list (POST /api/v1/onlinestream/episode-list)."""
    return await _req("POST", "/onlinestream/episode-list", json=payload)


async def seanime_stream_empty_cache() -> ReturnVal:
    """Empty online-stream cache (DELETE /api/v1/onlinestream/cache)."""
    return await _req("DELETE", "/onlinestream/cache")


async def seanime_stream_search(payload: dict) -> ReturnVal:
    """Manual online-stream search (POST /api/v1/onlinestream/search)."""
    return await _req("POST", "/onlinestream/search", json=payload)


async def seanime_stream_manual_mapping(payload: dict) -> ReturnVal:
    """Manual online-stream mapping (POST /api/v1/onlinestream/manual-mapping)."""
    return await _req("POST", "/onlinestream/manual-mapping", json=payload)


async def seanime_stream_get_mapping(payload: dict) -> ReturnVal:
    """Get online-stream mapping (POST /api/v1/onlinestream/get-mapping)."""
    return await _req("POST", "/onlinestream/get-mapping", json=payload)


async def seanime_stream_remove_mapping(payload: dict) -> ReturnVal:
    """Remove online-stream mapping (POST /api/v1/onlinestream/remove-mapping)."""
    return await _req("POST", "/onlinestream/remove-mapping", json=payload)


async def seanime_get_continuity_item(id: str) -> ReturnVal:
    """Get continuity watch history item (GET /api/v1/continuity/item/{id})."""
    return await _req("GET", f"/continuity/item/{_path(id)}")


async def seanime_update_continuity_item(payload: dict) -> ReturnVal:
    """Update continuity watch history item (PATCH /api/v1/continuity/item)."""
    return await _req("PATCH", "/continuity/item", json=payload)


async def seanime_get_continuity_history() -> ReturnVal:
    """Get continuity watch history (GET /api/v1/continuity/history)."""
    return await _req("GET", "/continuity/history")


# settings -------------------------------------------------------------------

async def seanime_get_settings() -> ReturnVal:
    """Get server settings (GET /api/v1/settings)."""
    return await _req("GET", "/settings")


async def seanime_save_settings(payload: dict) -> ReturnVal:
    """Save server settings (PATCH /api/v1/settings)."""
    return await _req("PATCH", "/settings", json=payload)


async def seanime_patch_setting(payload: dict) -> ReturnVal:
    """Patch a single setting (PATCH /api/v1/settings/path)."""
    return await _req("PATCH", "/settings/path", json=payload)


async def seanime_getting_started(payload: dict) -> ReturnVal:
    """Complete getting-started setup (POST /api/v1/start)."""
    return await _req("POST", "/start", json=payload)


async def seanime_save_autodl_settings(payload: dict) -> ReturnVal:
    """Save auto-downloader settings (PATCH /api/v1/settings/auto-downloader)."""
    return await _req("PATCH", "/settings/auto-downloader", json=payload)


async def seanime_save_mediaplayer_settings(payload: dict) -> ReturnVal:
    """Save media player settings (PATCH /api/v1/settings/media-player)."""
    return await _req("PATCH", "/settings/media-player", json=payload)


async def seanime_update_theme(payload: dict) -> ReturnVal:
    """Update UI theme (PATCH /api/v1/theme)."""
    return await _req("PATCH", "/theme", json=payload)


async def seanime_get_mediastream_settings() -> ReturnVal:
    """Get mediastream settings (GET /api/v1/mediastream/settings)."""
    return await _req("GET", "/mediastream/settings")


async def seanime_save_mediastream_settings(payload: dict) -> ReturnVal:
    """Save mediastream settings (PATCH /api/v1/mediastream/settings)."""
    return await _req("PATCH", "/mediastream/settings", json=payload)


async def seanime_get_torrentstream_settings() -> ReturnVal:
    """Get torrentstream settings (GET /api/v1/torrentstream/settings)."""
    return await _req("GET", "/torrentstream/settings")


async def seanime_save_torrentstream_settings(payload: dict) -> ReturnVal:
    """Save torrentstream settings (PATCH /api/v1/torrentstream/settings)."""
    return await _req("PATCH", "/torrentstream/settings", json=payload)


async def seanime_get_debrid_settings() -> ReturnVal:
    """Get debrid settings (GET /api/v1/debrid/settings)."""
    return await _req("GET", "/debrid/settings")


async def seanime_save_debrid_settings(payload: dict) -> ReturnVal:
    """Save debrid settings (PATCH /api/v1/debrid/settings)."""
    return await _req("PATCH", "/debrid/settings", json=payload)


async def seanime_get_dummy_debrid_settings() -> ReturnVal:
    """Get dummy debrid settings (GET /api/v1/debrid/dummy/settings)."""
    return await _req("GET", "/debrid/dummy/settings")


async def seanime_save_dummy_debrid_settings(payload: dict) -> ReturnVal:
    """Save dummy debrid settings (PATCH /api/v1/debrid/dummy/settings)."""
    return await _req("PATCH", "/debrid/dummy/settings", json=payload)


async def seanime_directory_selector(payload: dict) -> ReturnVal:
    """Browse server directories (POST /api/v1/directory-selector)."""
    return await _req("POST", "/directory-selector", json=payload)


async def seanime_mal_auth(payload: dict) -> ReturnVal:
    """Authenticate with MyAnimeList (POST /api/v1/mal/auth)."""
    return await _req("POST", "/mal/auth", json=payload)


async def seanime_mal_logout() -> ReturnVal:
    """Log out of MyAnimeList (POST /api/v1/mal/logout)."""
    return await _req("POST", "/mal/logout")


async def seanime_get_filecache_size() -> ReturnVal:
    """Get file cache total size (GET /api/v1/filecache/total-size)."""
    return await _req("GET", "/filecache/total-size")


async def seanime_remove_filecache_bucket(payload: dict) -> ReturnVal:
    """Remove file cache bucket (DELETE /api/v1/filecache/bucket)."""
    return await _req("DELETE", "/filecache/bucket", json=payload)


async def seanime_get_mediastream_cache_size() -> ReturnVal:
    """Get mediastream video files cache size (GET /api/v1/filecache/mediastream/videofiles/total-size)."""
    return await _req("GET", "/filecache/mediastream/videofiles/total-size")


async def seanime_clear_mediastream_cache() -> ReturnVal:
    """Clear mediastream video files cache (DELETE /api/v1/filecache/mediastream/videofiles)."""
    return await _req("DELETE", "/filecache/mediastream/videofiles")


async def seanime_set_discord_manga(payload: dict) -> ReturnVal:
    """Set Discord manga activity (POST /api/v1/discord/presence/manga)."""
    return await _req("POST", "/discord/presence/manga", json=payload)


async def seanime_set_discord_anime(payload: dict) -> ReturnVal:
    """Set Discord anime activity (POST /api/v1/discord/presence/anime)."""
    return await _req("POST", "/discord/presence/anime", json=payload)


async def seanime_set_discord_legacy_anime(payload: dict) -> ReturnVal:
    """Set Discord legacy anime activity (POST /api/v1/discord/presence/legacy-anime)."""
    return await _req("POST", "/discord/presence/legacy-anime", json=payload)


async def seanime_update_discord_anime(payload: dict) -> ReturnVal:
    """Update Discord anime activity (POST /api/v1/discord/presence/anime-update)."""
    return await _req("POST", "/discord/presence/anime-update", json=payload)


async def seanime_cancel_discord() -> ReturnVal:
    """Cancel Discord activity (POST /api/v1/discord/presence/cancel)."""
    return await _req("POST", "/discord/presence/cancel")


# sync -----------------------------------------------------------------------

async def seanime_get_tracked() -> ReturnVal:
    """Get tracked media items (GET /api/v1/local/track)."""
    return await _req("GET", "/local/track")


async def seanime_add_tracked(payload: dict) -> ReturnVal:
    """Track a media item (POST /api/v1/local/track)."""
    return await _req("POST", "/local/track", json=payload)


async def seanime_remove_tracked(payload: dict) -> ReturnVal:
    """Untrack a media item (DELETE /api/v1/local/track)."""
    return await _req("DELETE", "/local/track", json=payload)


async def seanime_is_tracked(id: str, type: str) -> ReturnVal:
    """Check if media is tracked (GET /api/v1/local/track/{id}/{type})."""
    return await _req("GET", f"/local/track/{_path(id)}/{_path(type)}")


async def seanime_sync_local(payload: dict) -> ReturnVal:
    """Sync local data (POST /api/v1/local/local)."""
    return await _req("POST", "/local/local", json=payload)


async def seanime_get_sync_queue() -> ReturnVal:
    """Get sync queue state (GET /api/v1/local/queue)."""
    return await _req("GET", "/local/queue")


async def seanime_sync_anilist(payload: dict) -> ReturnVal:
    """Sync AniList data (POST /api/v1/local/anilist)."""
    return await _req("POST", "/local/anilist", json=payload)


async def seanime_set_has_changes(payload: dict) -> ReturnVal:
    """Set local-changes flag (POST /api/v1/local/updated)."""
    return await _req("POST", "/local/updated", json=payload)


async def seanime_get_has_changes() -> ReturnVal:
    """Get local-changes flag (GET /api/v1/local/updated)."""
    return await _req("GET", "/local/updated")


async def seanime_get_storage_size() -> ReturnVal:
    """Get local storage size (GET /api/v1/local/storage/size)."""
    return await _req("GET", "/local/storage/size")


async def seanime_sync_simulated_to_anilist(payload: dict) -> ReturnVal:
    """Sync simulated data to AniList (POST /api/v1/local/sync-simulated-to-anilist)."""
    return await _req("POST", "/local/sync-simulated-to-anilist", json=payload)


async def seanime_set_offline(payload: dict) -> ReturnVal:
    """Set offline mode (POST /api/v1/local/offline)."""
    return await _req("POST", "/local/offline", json=payload)


# extensions -----------------------------------------------------------------

async def seanime_get_all_extensions(payload: dict) -> ReturnVal:
    """Get all extensions (POST /api/v1/extensions/all)."""
    return await _req("POST", "/extensions/all", json=payload)


async def seanime_get_extension_updates() -> ReturnVal:
    """Get extension update data (GET /api/v1/extensions/updates)."""
    return await _req("GET", "/extensions/updates")


async def seanime_list_extensions() -> ReturnVal:
    """List extension data (GET /api/v1/extensions/list)."""
    return await _req("GET", "/extensions/list")


async def seanime_get_extension_payload(id: str) -> ReturnVal:
    """Get extension payload (GET /api/v1/extensions/payload/{id})."""
    return await _req("GET", f"/extensions/payload/{_path(id)}")


async def seanime_get_marketplace(marketplace: str = None) -> ReturnVal:
    """Get marketplace extensions (GET /api/v1/extensions/marketplace)."""
    return await _req("GET", "/extensions/marketplace", params=_params(marketplace=marketplace))


async def seanime_list_manga_providers() -> ReturnVal:
    """List manga provider extensions (GET /api/v1/extensions/list/manga-provider)."""
    return await _req("GET", "/extensions/list/manga-provider")


async def seanime_list_stream_providers() -> ReturnVal:
    """List online-stream provider extensions (GET /api/v1/extensions/list/onlinestream-provider)."""
    return await _req("GET", "/extensions/list/onlinestream-provider")


async def seanime_list_torrent_providers() -> ReturnVal:
    """List anime torrent provider extensions (GET /api/v1/extensions/list/anime-torrent-provider)."""
    return await _req("GET", "/extensions/list/anime-torrent-provider")


async def seanime_list_episode_tabs() -> ReturnVal:
    """List anime entry episode tab extensions (GET /api/v1/extensions/list/anime-entry-episode-tabs)."""
    return await _req("GET", "/extensions/list/anime-entry-episode-tabs")


async def seanime_list_custom_sources() -> ReturnVal:
    """List custom source extensions (GET /api/v1/extensions/list/custom-source)."""
    return await _req("GET", "/extensions/list/custom-source")


async def seanime_list_dev_extensions() -> ReturnVal:
    """List development-mode extensions (GET /api/v1/extensions/list/development)."""
    return await _req("GET", "/extensions/list/development")


async def seanime_get_extension_user_config(id: str) -> ReturnVal:
    """Get extension user config (GET /api/v1/extensions/user-config/{id})."""
    return await _req("GET", f"/extensions/user-config/{_path(id)}")


async def seanime_save_extension_user_config(payload: dict) -> ReturnVal:
    """Save extension user config (POST /api/v1/extensions/user-config)."""
    return await _req("POST", "/extensions/user-config", json=payload)


async def seanime_get_plugin_settings() -> ReturnVal:
    """Get plugin settings (GET /api/v1/extensions/plugin-settings)."""
    return await _req("GET", "/extensions/plugin-settings")


async def seanime_set_pinned_trays(payload: dict) -> ReturnVal:
    """Set pinned plugin trays (POST /api/v1/extensions/plugin-settings/pinned-trays)."""
    return await _req("POST", "/extensions/plugin-settings/pinned-trays", json=payload)


async def seanime_custom_source_list_anime(payload: dict) -> ReturnVal:
    """List anime from a custom source provider (POST /api/v1/custom-source/provider/list/anime)."""
    return await _req("POST", "/custom-source/provider/list/anime", json=payload)


async def seanime_custom_source_list_manga(payload: dict) -> ReturnVal:
    """List manga from a custom source provider (POST /api/v1/custom-source/provider/list/manga)."""
    return await _req("POST", "/custom-source/provider/list/manga", json=payload)


# Resource groups for portmanteau registration. Every tool function name
# must appear in exactly one group - see test_all_seanime_grouped.
_GROUPS: dict[str, tuple[str, ...]] = {
    "seanime_system": (
        "seanime_check_for_updates",
        "seanime_delete_logs",
        "seanime_get_announcements",
        "seanime_get_changelog",
        "seanime_get_docs",
        "seanime_get_home_items",
        "seanime_get_latest_log",
        "seanime_get_latest_update",
        "seanime_get_log_content",
        "seanime_get_log_filenames",
        "seanime_get_memory_stats",
        "seanime_get_status",
        "seanime_get_theme",
        "seanime_update_home_items",
    ),
    "seanime_library": (
        "seanime_add_unknown_media",
        "seanime_delete_local_files",
        "seanime_delete_metadata_parent",
        "seanime_dump_local_files",
        "seanime_entry_bulk_action",
        "seanime_fetch_entry_suggestions",
        "seanime_get_anime_entry",
        "seanime_get_episode_collection",
        "seanime_get_file_tree",
        "seanime_get_library_collection",
        "seanime_get_local_files",
        "seanime_get_metadata_parent",
        "seanime_get_missing_episodes",
        "seanime_get_scan_summaries",
        "seanime_get_schedule",
        "seanime_get_silence_status",
        "seanime_get_upcoming_episodes",
        "seanime_import_local_files",
        "seanime_load_directory_children",
        "seanime_local_file_bulk_action",
        "seanime_manual_match",
        "seanime_populate_filler",
        "seanime_refresh_file_tree",
        "seanime_remove_empty_directories",
        "seanime_remove_filler",
        "seanime_save_metadata_parent",
        "seanime_scan",
        "seanime_super_update_local_files",
        "seanime_toggle_silence",
        "seanime_update_entry_progress",
        "seanime_update_entry_repeat",
        "seanime_update_local_file_data",
        "seanime_update_local_files",
    ),
    "seanime_anilist": (
        "seanime_delete_list_entry",
        "seanime_edit_list_entry",
        "seanime_get_anilist_collection",
        "seanime_get_anilist_stats",
        "seanime_get_cache_status",
        "seanime_get_media_details",
        "seanime_get_raw_anilist_collection",
        "seanime_get_raw_collection_tags",
        "seanime_get_studio_details",
        "seanime_list_anime",
        "seanime_list_missed_sequels",
        "seanime_list_recent_anime",
        "seanime_refresh_anilist_collection",
        "seanime_toggle_cache",
    ),
    "seanime_torrent": (
        "seanime_client_action",
        "seanime_client_details",
        "seanime_client_download",
        "seanime_client_get_files",
        "seanime_client_list",
        "seanime_client_rule_magnet",
        "seanime_create_autodl_profile",
        "seanime_create_autodl_rule",
        "seanime_debrid_add_torrents",
        "seanime_debrid_cancel_download",
        "seanime_debrid_cancel_stream",
        "seanime_debrid_delete_torrent",
        "seanime_debrid_download",
        "seanime_debrid_file_previews",
        "seanime_debrid_get_torrents",
        "seanime_debrid_start_stream",
        "seanime_debrid_torrent_info",
        "seanime_delete_autodl_item",
        "seanime_delete_autodl_profile",
        "seanime_delete_autodl_rule",
        "seanime_delete_autoselect_profile",
        "seanime_get_autodl_items",
        "seanime_get_autodl_profile",
        "seanime_get_autodl_profiles",
        "seanime_get_autodl_rule",
        "seanime_get_autodl_rules",
        "seanime_get_autodl_rules_by_anime",
        "seanime_get_autoselect_profile",
        "seanime_save_autoselect_profile",
        "seanime_search_torrent",
        "seanime_update_autodl_profile",
        "seanime_update_autodl_rule",
        "seanime_autodl_run",
        "seanime_autodl_run_simulation",
    ),
    "seanime_manga": (
        "seanime_manga_anilist_collection",
        "seanime_manga_anilist_list",
        "seanime_manga_anilist_raw",
        "seanime_manga_anilist_raw_tags",
        "seanime_manga_clear_download_queue",
        "seanime_manga_delete_downloaded_chapters",
        "seanime_manga_download_chapters",
        "seanime_manga_empty_entry_cache",
        "seanime_manga_get_chapters",
        "seanime_manga_get_collection",
        "seanime_manga_get_download_data",
        "seanime_manga_get_download_queue",
        "seanime_manga_get_downloaded_chapters",
        "seanime_manga_get_downloads",
        "seanime_manga_get_entry",
        "seanime_manga_get_entry_details",
        "seanime_manga_get_mapping",
        "seanime_manga_get_pages",
        "seanime_manga_get_preferences",
        "seanime_manga_get_source_refresh",
        "seanime_manga_import_preferences",
        "seanime_manga_latest_chapter_numbers",
        "seanime_manga_manual_mapping",
        "seanime_manga_manual_search",
        "seanime_manga_patch_preference",
        "seanime_manga_preview_mapping",
        "seanime_manga_refetch_chapters",
        "seanime_manga_remove_mapping",
        "seanime_manga_reset_errored_queue",
        "seanime_manga_start_download_queue",
        "seanime_manga_start_source_refresh",
        "seanime_manga_stop_download_queue",
        "seanime_manga_stop_source_refresh",
        "seanime_manga_update_progress",
    ),
    "seanime_playback": (
        "seanime_create_playlist",
        "seanime_delete_playlist",
        "seanime_get_continuity_history",
        "seanime_get_continuity_item",
        "seanime_get_playlist_episodes",
        "seanime_get_playlists",
        "seanime_playback_autoplay_next",
        "seanime_playback_cancel_manual_tracking",
        "seanime_playback_cancel_playlist",
        "seanime_playback_get_next_episode",
        "seanime_playback_play",
        "seanime_playback_play_next_episode",
        "seanime_playback_play_random",
        "seanime_playback_playlist_next",
        "seanime_playback_start_manual_tracking",
        "seanime_playback_start_playlist",
        "seanime_playback_sync_progress",
        "seanime_stream_empty_cache",
        "seanime_stream_get_episode_list",
        "seanime_stream_get_episode_source",
        "seanime_stream_get_mapping",
        "seanime_stream_manual_mapping",
        "seanime_stream_remove_mapping",
        "seanime_stream_search",
        "seanime_update_continuity_item",
        "seanime_update_playlist",
    ),
    "seanime_settings": (
        "seanime_cancel_discord",
        "seanime_clear_mediastream_cache",
        "seanime_directory_selector",
        "seanime_get_debrid_settings",
        "seanime_get_dummy_debrid_settings",
        "seanime_get_filecache_size",
        "seanime_get_mediastream_cache_size",
        "seanime_get_mediastream_settings",
        "seanime_get_settings",
        "seanime_get_torrentstream_settings",
        "seanime_getting_started",
        "seanime_mal_auth",
        "seanime_mal_logout",
        "seanime_patch_setting",
        "seanime_remove_filecache_bucket",
        "seanime_save_autodl_settings",
        "seanime_save_debrid_settings",
        "seanime_save_dummy_debrid_settings",
        "seanime_save_mediaplayer_settings",
        "seanime_save_mediastream_settings",
        "seanime_save_settings",
        "seanime_save_torrentstream_settings",
        "seanime_set_discord_anime",
        "seanime_set_discord_legacy_anime",
        "seanime_set_discord_manga",
        "seanime_update_discord_anime",
        "seanime_update_theme",
    ),
    "seanime_sync": (
        "seanime_add_tracked",
        "seanime_get_has_changes",
        "seanime_get_storage_size",
        "seanime_get_sync_queue",
        "seanime_get_tracked",
        "seanime_is_tracked",
        "seanime_remove_tracked",
        "seanime_set_has_changes",
        "seanime_set_offline",
        "seanime_sync_anilist",
        "seanime_sync_local",
        "seanime_sync_simulated_to_anilist",
    ),
    "seanime_extensions": (
        "seanime_custom_source_list_anime",
        "seanime_custom_source_list_manga",
        "seanime_get_all_extensions",
        "seanime_get_extension_payload",
        "seanime_get_extension_updates",
        "seanime_get_extension_user_config",
        "seanime_get_marketplace",
        "seanime_get_plugin_settings",
        "seanime_list_custom_sources",
        "seanime_list_dev_extensions",
        "seanime_list_episode_tabs",
        "seanime_list_extensions",
        "seanime_list_manga_providers",
        "seanime_list_stream_providers",
        "seanime_list_torrent_providers",
        "seanime_save_extension_user_config",
        "seanime_set_pinned_trays",
    ),
}


def _op_line(name: str, fn: Any) -> str:
    """One line of a group tool's description: signature + one-line doc."""
    sig = ", ".join(
        p.name if p.default is inspect.Parameter.empty else f"{p.name}={p.default!r}"
        for p in inspect.signature(fn).parameters.values()
    )
    return f"- {name}({sig}) - {' '.join((fn.__doc__ or '').split())}"


def _register_group(
    group: str, names: tuple[str, ...], ns: dict[str, Any], readonly_names: set[str]
) -> None:
    """Register one dispatching tool that fans out to every function named
    in `names`. The functions themselves are untouched - they're just
    looked up by name instead of each becoming its own tool."""
    fns = {n: ns[n] for n in names}

    async def dispatch(
        operation: str, arguments: JSONObj | None = None
    ) -> ReturnVal:
        fn = fns.get(operation)
        if fn is None:
            raise ToolError(
                f"Unknown operation {operation!r} for {group}. Valid: {', '.join(fns)}"
            )
        return await fn(**(arguments or {}))

    dispatch.__annotations__["operation"] = Literal[names]
    ann = READONLY if set(names) <= readonly_names else None
    mcp.add_tool(
        Tool.from_function(
            dispatch,
            name=group,
            description=(
                f"{group.replace('_', ' ')} operations on Seanime. Pass `operation` and an "
                f"`arguments` dict matching that operation's parameters.\n\n"
                + "\n".join(_op_line(n, f) for n, f in fns.items())
            ),
            annotations=ann,
        )
    )


def _register_tools() -> None:
    ns = globals()
    readonly_names: set[str] = {
        "seanime_check_for_updates",
        "seanime_dump_local_files",
        "seanime_get_all_extensions",
        "seanime_get_anilist_collection",
        "seanime_get_anilist_stats",
        "seanime_get_anime_entry",
        "seanime_get_autodl_items",
        "seanime_get_autodl_profile",
        "seanime_get_autodl_profiles",
        "seanime_get_autodl_rule",
        "seanime_get_autodl_rules",
        "seanime_get_autodl_rules_by_anime",
        "seanime_get_autoselect_profile",
        "seanime_get_cache_status",
        "seanime_get_changelog",
        "seanime_get_continuity_history",
        "seanime_get_continuity_item",
        "seanime_get_debrid_settings",
        "seanime_get_docs",
        "seanime_get_dummy_debrid_settings",
        "seanime_get_episode_collection",
        "seanime_get_extension_payload",
        "seanime_get_extension_updates",
        "seanime_get_extension_user_config",
        "seanime_get_file_tree",
        "seanime_get_filecache_size",
        "seanime_get_has_changes",
        "seanime_get_home_items",
        "seanime_get_latest_log",
        "seanime_get_latest_update",
        "seanime_get_library_collection",
        "seanime_get_local_files",
        "seanime_get_log_content",
        "seanime_get_log_filenames",
        "seanime_get_marketplace",
        "seanime_get_media_details",
        "seanime_get_mediastream_cache_size",
        "seanime_get_mediastream_settings",
        "seanime_get_memory_stats",
        "seanime_get_metadata_parent",
        "seanime_get_missing_episodes",
        "seanime_get_playlist_episodes",
        "seanime_get_playlists",
        "seanime_get_plugin_settings",
        "seanime_get_raw_anilist_collection",
        "seanime_get_raw_collection_tags",
        "seanime_get_scan_summaries",
        "seanime_get_schedule",
        "seanime_get_settings",
        "seanime_get_silence_status",
        "seanime_get_status",
        "seanime_get_storage_size",
        "seanime_get_studio_details",
        "seanime_get_sync_queue",
        "seanime_get_theme",
        "seanime_get_torrentstream_settings",
        "seanime_get_tracked",
        "seanime_get_upcoming_episodes",
        "seanime_is_tracked",
        "seanime_list_anime",
        "seanime_list_custom_sources",
        "seanime_list_dev_extensions",
        "seanime_list_episode_tabs",
        "seanime_list_extensions",
        "seanime_list_manga_providers",
        "seanime_list_missed_sequels",
        "seanime_list_recent_anime",
        "seanime_list_stream_providers",
        "seanime_list_torrent_providers",
        "seanime_manga_anilist_collection",
        "seanime_manga_anilist_list",
        "seanime_manga_anilist_raw",
        "seanime_manga_anilist_raw_tags",
        "seanime_manga_get_chapters",
        "seanime_manga_get_collection",
        "seanime_manga_get_download_data",
        "seanime_manga_get_download_queue",
        "seanime_manga_get_downloaded_chapters",
        "seanime_manga_get_downloads",
        "seanime_manga_get_entry",
        "seanime_manga_get_entry_details",
        "seanime_manga_get_mapping",
        "seanime_manga_get_pages",
        "seanime_manga_get_preferences",
        "seanime_manga_get_source_refresh",
        "seanime_manga_latest_chapter_numbers",
        "seanime_manga_manual_search",
        "seanime_manga_preview_mapping",
        "seanime_client_details",
        "seanime_client_list",
        "seanime_custom_source_list_anime",
        "seanime_custom_source_list_manga",
        "seanime_debrid_file_previews",
        "seanime_debrid_get_torrents",
        "seanime_debrid_torrent_info",
        "seanime_playback_get_next_episode",
        "seanime_stream_get_episode_list",
        "seanime_stream_get_episode_source",
        "seanime_stream_get_mapping",
        "seanime_stream_search",
    }
    for group, names in _GROUPS.items():
        _register_group(group, names, ns, readonly_names)


_register_tools()


def main() -> None:
    global _client
    url = os.environ.get("SEANIME_URL")
    if not url:
        print(
            "SEANIME_URL environment variable is required (e.g. http://10.10.10.30:43211)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    api_key = os.environ.get("SEANIME_API_KEY") or os.environ.get("SEANIME_TOKEN")
    _client = build_client(url, api_key)
    mcp.run()


if __name__ == "__main__":
    main()
