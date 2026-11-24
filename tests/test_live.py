"""Opt-in smoke tests for a live Seanime instance (read-only)."""

import os

import pytest
from fastmcp import Client

import seanime_mcp

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("SEANIME_URL"),
        reason="requires SEANIME_URL (and SEANIME_API_KEY when a server password is set)",
    ),
]


@pytest.fixture(autouse=True)
def configure_client():
    seanime_mcp._client = seanime_mcp.build_client(
        os.environ["SEANIME_URL"],
        os.environ.get("SEANIME_API_KEY") or os.environ.get("SEANIME_TOKEN"),
    )
    yield


async def call(group, operation, **arguments):
    async with Client(seanime_mcp.mcp) as client:
        return await client.call_tool(
            group, {"operation": operation, "arguments": arguments}
        )


async def test_status():
    result = await call("seanime_system", "seanime_get_status")
    assert result.data is not None


async def test_settings_and_theme():
    assert (await call("seanime_settings", "seanime_get_settings")).data is not None
    assert (await call("seanime_system", "seanime_get_theme")).data is not None


async def test_library_reads():
    assert (await call("seanime_library", "seanime_get_local_files")).data is not None
    assert (await call("seanime_library", "seanime_get_missing_episodes")).data is not None
