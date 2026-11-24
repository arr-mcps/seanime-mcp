# AGENTS.md - seanime-mcp

MCP server exposing Seanime's REST API as 9 resource-scoped portmanteau
tools (211 operations). Uses FastMCP, `uv` for deps. Tested against Seanime
3.10.5 (the version running in CT 126 on the new box).

## Tool design

Exactly 9 tools are registered, one per entry in `_GROUPS` in
`seanime_mcp.py`: `seanime_system`, `seanime_library`, `seanime_anilist`,
`seanime_torrent`, `seanime_manga`, `seanime_playback`,
`seanime_settings`, `seanime_sync`, `seanime_extensions`. Each tool takes an
`operation` (a `Literal` of its functions' names) plus an `arguments` dict
and dispatches to a plain async endpoint function. Do not register
individual endpoint functions as tools. See the arr-mcps masterlist
`AGENTS.md` for the rationale (a 211-tool server blows the MCP context
budget).

No group is marked `readOnlyHint=True`: every group contains at least one
write operation, so all groups carry no hints (mixed groups carry no hints
per the standard). A `readonly_names` set is still maintained for the
read-only operations; it currently qualifies no whole group.

`dispatch` returns `ReturnVal = JSONObj | list[Any] | str | int | float | bool | None`
because Seanime returns raw text scalars on some endpoints. FastMCP
validates the declared return type, so do not narrow it.

The endpoint list and canonical paths came from the upstream source at
`internal/handlers/routes.go` (Seanime 3.10.x, cloned for reference during
scaffolding - not vendored here). Parameter shapes: path/query params were
read from each handler's `c.Param`/`c.QueryParam` calls; POST/PATCH/DELETE
bodies are pass-through `payload` dicts matching the running version's
DTOs. If Seanime is upgraded, re-check `routes.go` plus the handler files
before adding endpoints.

Deliberately excluded: binary/streaming endpoints (`/mediastream/*`,
`/directstream/*`, `/proxy`, `/image-proxy`, nakama streams, websocket
`/events`), which return media bytes or never-ending streams, not JSON;
server self-update (`install-update`, `download-release`,
`download-mac-denshi-update`); local-machine side effects
(`open-in-explorer`, `start media player`, `test-dump`); the torrent-file
challenge download (`/download-torrent-file` needs a web-UI client session).
Do not place real API keys, passwords, or tokens in tool descriptions or
commit messages.

## Auth

Seanime has no login-token endpoint for API clients. Requests authenticate
with the `X-Seanime-Token` header, which the server compares against the
SHA256 hex of the configured server password (`ServerPasswordHash` in
upstream `internal/core/app.go`). So `SEANIME_API_KEY` must be set to
`sha256hex(server password)`, e.g.:

```bash
export SEANIME_API_KEY=$(python3 -c "import hashlib,os; print(hashlib.sha256(os.environ['PW'].encode()).hexdigest())")
```

## Testing

- Offline suite: `make test` (or `uv run pytest`)
- Live integration (needs `SEANIME_URL` + `SEANIME_API_KEY`): `make test-integration`
- `tests/test_tools.py` has exact request-shape assertions for a subset, a
  generic smoke test that executes every endpoint function through its group
  with type-appropriate dummy arguments, and `test_all_seanime_grouped`,
  which asserts every endpoint function appears in exactly one `_GROUPS` entry.
- Live tests are read-only (`status`, `settings`, `theme`, `local-files`,
  `missing-episodes`). Never trigger library scans, downloads, or entry
  mutations against the live service from tests.

## Release workflow

Use `make bump-*` (`uv version --bump patch|minor|major`), which updates
`pyproject.toml` and `uv.lock` together. Never hand-edit the version. Commit
message is just the version, tag `v<version>`, then push main and the tag.
Each server is its own git repo.
