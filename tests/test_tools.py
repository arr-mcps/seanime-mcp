"""Offline contract tests for the Seanime MCP tools."""

import base64
import inspect
import json

import httpx
import pytest
import pytest_asyncio
from fastmcp import Client
from fastmcp.exceptions import ToolError

import seanime_mcp


class Recorder:
    def __init__(self):
        self.method = None
        self.url = None
        self.headers = None
        self.json = None
        self.raw = None
        self.response = httpx.Response(200, json={"ok": True})

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.method = request.method
        self.url = request.url
        self.headers = request.headers
        self.raw = request.content
        try:
            self.json = json.loads(request.content) if request.content else None
        except ValueError:
            self.json = None
        return self.response


@pytest.fixture
def recorder():
    return Recorder()


@pytest_asyncio.fixture
async def server(recorder, monkeypatch):
    client = seanime_mcp.build_client(
        "http://10.10.10.30:43211",
        "test-key",
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(seanime_mcp, "_client", client)
    yield seanime_mcp.mcp
    await client.aclose()


_OP_GROUP = {
    op: group for group, ops in seanime_mcp._GROUPS.items() for op in ops
}


async def call(server, op_name, **kwargs):
    """Call `op_name` (an operation name) through its portmanteau tool."""
    async with Client(server) as client:
        return await client.call_tool(
            _OP_GROUP[op_name], {"operation": op_name, "arguments": kwargs}
        )


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path"),
    [
        ("seanime_get_status", {}, "GET", "/api/v1/status"),
        ("seanime_get_library_collection", {}, "GET", "/api/v1/library/collection"),
        ("seanime_get_schedule", {}, "GET", "/api/v1/library/schedule"),
        ("seanime_get_missing_episodes", {}, "GET", "/api/v1/library/missing-episodes"),
        ("seanime_get_upcoming_episodes", {}, "GET", "/api/v1/library/upcoming-episodes"),
        (
            "seanime_get_anime_entry",
            {"id": 1},
            "GET",
            "/api/v1/library/anime-entry/1",
        ),
        (
            "seanime_get_silence_status",
            {"id": 5},
            "GET",
            "/api/v1/library/anime-entry/silence/5",
        ),
        (
            "seanime_get_episode_collection",
            {"id": 21},
            "GET",
            "/api/v1/anime/episode-collection/21",
        ),
        ("seanime_get_anilist_collection", {}, "GET", "/api/v1/anilist/collection"),
        (
            "seanime_get_media_details",
            {"id": 21},
            "GET",
            "/api/v1/anilist/media-details/21",
        ),
        (
            "seanime_get_studio_details",
            {"id": 14},
            "GET",
            "/api/v1/anilist/studio-details/14",
        ),
        ("seanime_list_missed_sequels", {}, "GET", "/api/v1/anilist/list-missed-sequels"),
        ("seanime_get_anilist_stats", {}, "GET", "/api/v1/anilist/stats"),
        ("seanime_get_autodl_rules", {}, "GET", "/api/v1/auto-downloader/rules"),
        (
            "seanime_get_autodl_rule",
            {"id": "abc"},
            "GET",
            "/api/v1/auto-downloader/rule/abc",
        ),
        (
            "seanime_delete_autodl_rule",
            {"id": "abc"},
            "DELETE",
            "/api/v1/auto-downloader/rule/abc",
        ),
        ("seanime_client_list", {}, "GET", "/api/v1/torrent-client/list"),
        ("seanime_debrid_get_torrents", {}, "GET", "/api/v1/debrid/torrents"),
        ("seanime_get_playlists", {}, "GET", "/api/v1/playlists"),
        (
            "seanime_get_playlist_episodes",
            {"id": "pl1"},
            "GET",
            "/api/v1/playlist/episodes/pl1",
        ),
        (
            "seanime_get_continuity_item",
            {"id": "x"},
            "GET",
            "/api/v1/continuity/item/x",
        ),
        ("seanime_get_settings", {}, "GET", "/api/v1/settings"),
        ("seanime_get_theme", {}, "GET", "/api/v1/theme"),
        ("seanime_get_mediastream_settings", {}, "GET", "/api/v1/mediastream/settings"),
        ("seanime_get_tracked", {}, "GET", "/api/v1/local/track"),
        (
            "seanime_is_tracked",
            {"id": "1", "type": "anime"},
            "GET",
            "/api/v1/local/track/1/anime",
        ),
        ("seanime_list_extensions", {}, "GET", "/api/v1/extensions/list"),
        (
            "seanime_get_extension_payload",
            {"id": "ext-1"},
            "GET",
            "/api/v1/extensions/payload/ext-1",
        ),
        ("seanime_manga_get_collection", {}, "GET", "/api/v1/manga/collection"),
        (
            "seanime_manga_get_entry",
            {"id": 100},
            "GET",
            "/api/v1/manga/entry/100",
        ),
        (
            "seanime_manga_patch_preference",
            {"media_id": 100, "payload": {}},
            "PATCH",
            "/api/v1/manga/preferences/100",
        ),
        ("seanime_manga_get_download_queue", {}, "GET", "/api/v1/manga/download-queue"),
        ("seanime_delete_logs", {}, "DELETE", "/api/v1/logs"),
    ],
)
async def test_endpoint_routes(server, recorder, name, kwargs, method, path):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.raw_path.split(b"?")[0].decode() == path


@pytest.mark.parametrize(
    ("name", "kwargs", "method", "path", "body"),
    [
        (
            "seanime_update_home_items",
            {"payload": {"items": []}},
            "POST",
            "/api/v1/status/home-items",
            {"items": []},
        ),
        (
            "seanime_scan",
            {"payload": {"enhanced": True}},
            "POST",
            "/api/v1/library/scan",
            {"enhanced": True},
        ),
        (
            "seanime_entry_bulk_action",
            {"payload": {"mediaId": 1, "action": "unmatch"}},
            "PATCH",
            "/api/v1/library/anime-entry/bulk-action",
            {"mediaId": 1, "action": "unmatch"},
        ),
        (
            "seanime_edit_list_entry",
            {"payload": {"mediaId": 21}},
            "POST",
            "/api/v1/anilist/list-entry",
            {"mediaId": 21},
        ),
        (
            "seanime_search_torrent",
            {"payload": {"query": "frieren"}},
            "POST",
            "/api/v1/torrent/search",
            {"query": "frieren"},
        ),
        (
            "seanime_create_autodl_rule",
            {"payload": {"name": "r"}},
            "POST",
            "/api/v1/auto-downloader/rule",
            {"name": "r"},
        ),
        (
            "seanime_save_settings",
            {"payload": {"library": {}}},
            "PATCH",
            "/api/v1/settings",
            {"library": {}},
        ),
        (
            "seanime_create_playlist",
            {"payload": {"name": "p"}},
            "POST",
            "/api/v1/playlist",
            {"name": "p"},
        ),
        (
            "seanime_stream_search",
            {"payload": {"query": "x"}},
            "POST",
            "/api/v1/onlinestream/search",
            {"query": "x"},
        ),
        (
            "seanime_manga_get_chapters",
            {"payload": {"mediaId": 1}},
            "POST",
            "/api/v1/manga/chapters",
            {"mediaId": 1},
        ),
        (
            "seanime_delete_local_files",
            {"payload": {"paths": []}},
            "DELETE",
            "/api/v1/library/local-files",
            {"paths": []},
        ),
    ],
)
async def test_request_bodies(server, recorder, name, kwargs, method, path, body):
    await call(server, name, **kwargs)
    assert recorder.method == method
    assert recorder.url.path == path
    assert recorder.json == body


async def test_query_parameters(server, recorder):
    await call(server, "seanime_client_list", category="anime", sort="name")
    assert recorder.url.params["category"] == "anime"
    assert recorder.url.params["sort"] == "name"


async def test_changelog_query_parameters(server, recorder):
    await call(server, "seanime_get_changelog", after="v3.0", before="v3.1")
    assert recorder.url.params["after"] == "v3.0"
    assert recorder.url.params["before"] == "v3.1"


async def test_api_key_header(server, recorder):
    await call(server, "seanime_get_status")
    assert recorder.headers["x-seanime-token"] == "test-key"


async def test_no_api_key_header(recorder, monkeypatch):
    client = seanime_mcp.build_client(
        "http://10.10.10.30:43211",
        None,
        transport=httpx.MockTransport(recorder.handler),
    )
    monkeypatch.setattr(seanime_mcp, "_client", client)
    await call(seanime_mcp.mcp, "seanime_get_status")
    assert "x-seanime-token" not in recorder.headers
    await client.aclose()


async def test_text_scalar_response(server, recorder):
    recorder.response = httpx.Response(
        200, text="3.10.5", headers={"content-type": "text/html"}
    )
    result = await call(server, "seanime_get_latest_update")
    assert result.data == "3.10.5"


async def test_list_returning_tool(server, recorder):
    recorder.response = httpx.Response(200, json=[{"id": 1}, {"id": 2}])
    result = await call(server, "seanime_get_playlists")
    assert result.structured_content == {"result": [{"id": 1}, {"id": 2}]}
    assert result.data is not None


async def test_error_message(server, recorder):
    recorder.response = httpx.Response(401, text='{"error":"UNAUTHENTICATED"}')
    with pytest.raises(ToolError, match="401.*UNAUTHENTICATED"):
        await call(server, "seanime_get_status")


async def test_non_json_error(server, recorder):
    recorder.response = httpx.Response(502, text="<html>Bad Gateway</html>")
    with pytest.raises(ToolError, match="502"):
        await call(server, "seanime_get_status")


def test_main_requires_url(monkeypatch):
    monkeypatch.delenv("SEANIME_URL", raising=False)
    with pytest.raises(SystemExit):
        seanime_mcp.main()


# --- full-surface smoke coverage ---------------------------------------------
# Only a subset of the 211 operations has exact request-shape assertions above.
# This exercises every endpoint function's URL-templating/body-marshaling path
# with type-appropriate dummy arguments, so all grouped operations are covered.

ALL_ENDPOINT_NAMES = sorted(
    name
    for name in dir(seanime_mcp)
    if name.startswith("seanime_")
    and inspect.iscoroutinefunction(getattr(seanime_mcp, name))
)


def _sample_value(param: inspect.Parameter):
    ann = str(param.annotation)
    if "dict" in ann:
        return {}
    if "list" in ann:
        return []
    if "bool" in ann:
        return True
    if "int" in ann:
        return 1
    if "float" in ann:
        return 1
    return "x"


@pytest.mark.parametrize("name", ALL_ENDPOINT_NAMES)
async def test_every_endpoint_is_callable(server, recorder, name):
    fn = getattr(seanime_mcp, name)
    kwargs = {
        p.name: _sample_value(p)
        for p in inspect.signature(fn).parameters.values()
        if p.default is inspect.Parameter.empty
    }
    await call(server, name, **kwargs)
    assert recorder.method in ("GET", "POST", "PUT", "PATCH", "DELETE")
    assert recorder.url.path.startswith("/")


# --- portmanteau grouping safety net ------------------------------------------

def test_all_seanime_grouped():
    """Every endpoint function must land in exactly one portmanteau group."""
    grouped_names = [n for names in seanime_mcp._GROUPS.values() for n in names]
    assert sorted(grouped_names) == sorted(ALL_ENDPOINT_NAMES)
    assert len(grouped_names) == len(set(grouped_names))


async def test_group_tools_are_the_only_registered_tools(server):
    async with Client(server) as client:
        tools = await client.list_tools()
    assert {tool.name for tool in tools} == set(seanime_mcp._GROUPS)


async def test_unknown_operation_rejected_by_schema(server):
    # The Literal[...] enum on `operation` means an invalid value never reaches
    # _register_group's dispatch body - pydantic rejects it first.
    with pytest.raises(ToolError, match="validation error"):
        async with Client(server) as client:
            await client.call_tool("seanime_library", {"operation": "not_real"})
