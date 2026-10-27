import asyncio
import json
import os
import sys

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SURFER_MCP_TEST_COM") != "1",
    reason="Set SURFER_MCP_TEST_COM=1 to run the MCP stdio integration test.",
)


def test_mcp_server_over_stdio(tmp_path):
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    (tmp_path / "data.csv").write_text(
        "X,Y,Z\n"
        "0,0,10\n1000,0,20\n0,1000,30\n1000,1000,40\n"
        "500,500,25\n250,750,35\n750,250,15\n250,250,5\n",
        encoding="utf-8",
    )
    env = {**os.environ, "SURFER_MCP_WORKSPACE": str(tmp_path), "SURFER_MCP_VISIBLE": "0"}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "surfer_mcp"], env=env, cwd=str(tmp_path)
    )

    async def scenario():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                tools = await client.list_tools()
                names = {tool.name for tool in tools.tools}
                assert {
                    "surfer_status",
                    "create_grid",
                    "create_contour_map",
                    "create_cross_section",
                    "create_surface_map",
                    "export_document",
                    "save_plot",
                } <= names

                result = await client.call_tool("surfer_status", {})
                status = json.loads(result.content[0].text)
                assert status["ok"] is True

                grid = await client.call_tool(
                    "create_grid",
                    {"data_file": "data.csv", "cols": 80, "rows": 60, "algorithm": "idw"},
                )
                grid_payload = json.loads(grid.content[0].text)
                assert grid_payload["ok"] is True, grid_payload
                assert (tmp_path / "grids" / "data.grd").is_file()

                map_result = await client.call_tool(
                    "create_contour_map",
                    {"grid_file": "grids/data.grd", "output_image": "map.png"},
                )
                map_payload = json.loads(map_result.content[0].text)
                assert map_payload["ok"] is True, map_payload
                assert (tmp_path / "map.png").is_file()

    asyncio.run(scenario())
