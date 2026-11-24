# seanime-mcp

An MCP server exposing [Seanime](https://github.com/5rahim/seanime)'s REST
API as tools for managing the anime/manga library, AniList entries, torrent
search and clients, auto-downloader rules, playback, extensions, and server
settings.

## Requirements

- Seanime with its REST API reachable (tested against 3.10.5)
- Python 3.11+ and `uv` for source development

## Configuration

| Variable | Required | Description |
| --- | --- | --- |
| `SEANIME_URL` | Yes | Seanime base URL, for example `http://10.10.10.30:43211`. The server appends `/api/v1`. |
| `SEANIME_API_KEY` | Yes (when a server password is set) | Value sent as `X-Seanime-Token`. This is the SHA256 hex of the server password. `SEANIME_TOKEN` is accepted as a fallback name. |

Install the tool and register it with Claude Code:

```bash
uv tool install seanime_mcp-*.whl
claude mcp add seanime \
  --env SEANIME_URL=http://10.10.10.30:43211 \
  --env SEANIME_API_KEY=<sha256-hex-of-server-password> \
  -- seanime-mcp
```

For a source checkout:

```bash
uv sync
claude mcp add seanime \
  --env SEANIME_URL=http://10.10.10.30:43211 \
  --env SEANIME_API_KEY=<sha256-hex-of-server-password> \
  -- uv run --directory /path/to/seanime-mcp seanime-mcp
```

## Tools

**9 resource-scoped tools** cover all 211 Seanime REST operations via an
`operation` parameter. Call a tool with `operation` set to one of its listed
operations and an `arguments` dict matching that operation's parameters. Each
tool's own description (visible to your MCP client) lists every operation, its
signature, and a one-line doc, so no discovery round-trip is needed. This keeps
the whole API available while costing a fraction of the context budget of
registering 211 endpoints as separate tools.

| Tool | Operations | Covers |
| --- | --- | --- |
| `seanime_torrent` | 34 | Torrent search, torrent-client control, auto-downloader rules/items/profiles, auto-select, debrid torrents and streams |
| `seanime_manga` | 34 | AniList manga collection, manga entries/chapters/pages, downloads and queue, source refresh, manual search and mapping |
| `seanime_library` | 33 | Local files, library collection, schedule, missing/upcoming episodes, entry matching and progress, scan, explorer, filler metadata |
| `seanime_settings` | 27 | Server settings, theme, mediastream/torrentstream/debrid settings, MAL auth, file cache, Discord presence |
| `seanime_playback` | 26 | Playback manager, playlists, online-stream sources and mappings, continuity history |
| `seanime_system` | 14 | Status, home items, announcements, updates, changelog, logs, memory stats, theme, API docs |
| `seanime_anilist` | 14 | AniList collection, media/studio details, list entries, browse, missed sequels, stats, cache layer |
| `seanime_extensions` | 17 | Extension data, payloads, marketplace, provider lists, user config, plugin settings, custom sources |
| `seanime_sync` | 12 | Local tracked media, sync queue, AniList sync, offline mode |

Endpoint-level naming (`seanime_<area>_<verb>_<resource>`) is kept as the
`operation` value, so the full endpoint list is discoverable from each
group tool's description at runtime. No group is marked read-only; every
group contains write operations.

Example:

```text
seanime_system(operation="seanime_get_status", arguments={})
seanime_library(operation="seanime_get_missing_episodes", arguments={})
seanime_torrent(operation="seanime_search_torrent", arguments={"payload": {"query": "frieren"}})
```

Notes on special operations:

- Body payloads are pass-through JSON dictionaries matching the DTOs of the
  running Seanime version. Do not put real API keys, passwords, or tokens
  in prompts.
- Binary/streaming endpoints (mediastream, directstream, proxy, image-proxy,
  websocket events, nakama streams) are not exposed - they return media bytes
  or never-ending streams, not JSON.
- Server self-update and local-machine actions (open-in-explorer, start media
  player) are excluded.

## Development

```bash
make sync
make test
make test-integration   # requires SEANIME_URL and SEANIME_API_KEY
make build
```

The offline tests use `httpx.MockTransport`; integration tests are skipped by
default.
