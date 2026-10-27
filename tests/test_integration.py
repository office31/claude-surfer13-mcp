import asyncio
import math
import os
import random

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("SURFER_MCP_TEST_COM") != "1",
    reason="Set SURFER_MCP_TEST_COM=1 to run Surfer COM integration tests.",
)


@pytest.fixture()
def session(tmp_path):
    from surfer_mcp.surfer import SurferSession

    instance = SurferSession(workspace=tmp_path, visible=False)
    try:
        yield instance
    finally:
        instance.quit()


def _write_points(path, count=400):
    random.seed(123)
    lines = ["X,Y,Z"]
    for _ in range(count):
        x = random.uniform(0, 5000)
        y = random.uniform(0, 4000)
        z = 100 + 0.03 * y + 80 * math.sin(x / 900.0) + random.uniform(-5, 5)
        lines.append(f"{x:.2f},{y:.2f},{z:.2f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_surfer_full_pipeline(session, tmp_path):
    (tmp_path / "out").mkdir()
    data = tmp_path / "points.csv"
    _write_points(data)

    async def scenario():
        grid = await session.run(
            lambda: session.create_grid(
                "points.csv", output_grid="grids/test.grd", cols=140, rows=110
            )
        )
        assert grid["points"] == 400
        assert grid["algorithm"] == "kriging"
        assert (tmp_path / "grids" / "test.grd").is_file()

        map_result = await session.run(
            lambda: session.create_contour_map(
                "grids/test.grd",
                title="Carte structurale",
                output_image="out/map.png",
                save_plot="out/map.srf",
            )
        )
        assert (tmp_path / "out" / "map.png").stat().st_size > 0
        assert (tmp_path / "out" / "map.srf").stat().st_size > 0

        section = await session.run(
            lambda: session.create_cross_section(
                "grids/test.grd",
                start_x=600,
                start_y=500,
                end_x=4400,
                end_y=3200,
                title="Coupe A-A'",
                vertical_exaggeration=2.5,
                output_image="out/section.png",
                save_profile_data="out/section.dat",
            )
        )
        assert (tmp_path / "out" / "section.png").stat().st_size > 0
        assert section["profile_data"]["size_bytes"] > 0

        surface = await session.run(
            lambda: session.create_surface_map("grids/test.grd", output_image="out/surface.png")
        )
        assert (tmp_path / "out" / "surface.png").stat().st_size > 0

        documents = await session.run(session.list_documents)
        assert documents["count"] >= 3

        exported = await session.run(
            lambda: session.export_document(map_result["document"], "out/map.pdf")
        )
        assert (tmp_path / "out" / "map.pdf").stat().st_size > 0
        assert exported["path"].endswith("map.pdf")

        saved = await session.run(
            lambda: session.save_plot(map_result["document"], "out/map_copy.srf")
        )
        assert saved["path"].endswith("map_copy.srf")

        for name in (saved["document"], section["document"], surface["document"]):
            await session.run(lambda name=name: session.close_document(name))

        remaining = await session.run(session.list_documents)
        assert remaining["count"] == 0

    asyncio.run(scenario())
