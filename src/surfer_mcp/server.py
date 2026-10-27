from __future__ import annotations

import json
import logging
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

from . import __version__
from .surfer import SurferError, SurferSession

logger = logging.getLogger("surfer_mcp")

mcp = MCPServer(
    name="surfer",
    version=__version__,
    instructions=(
        "Automate Golden Software Surfer 13+ on Windows. Paths passed to tools are resolved "
        "against the workspace directory (SURFER_MCP_WORKSPACE). Typical workflow: "
        "1) create_grid from an XYZ CSV/TXT file, 2) create_contour_map, create_cross_section "
        "or create_surface_map, 3) export or save the open document. "
        "Columns are 1-based; coordinates use the project's map units."
    ),
)

session = SurferSession()

Algorithm = Literal[
    "kriging",
    "idw",
    "min_curvature",
    "shepards",
    "natural_neighbor",
    "nearest_neighbor",
    "regression",
    "radial_basis",
    "triangulation",
    "moving_average",
    "data_metrics",
    "local_polynomial",
]
MapStyle = Literal["color", "lines", "filled"]


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


async def _call(action) -> str:
    try:
        payload = await session.run(action)
    except SurferError as exc:
        return _json({"ok": False, "error": str(exc)})
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors to the model
        logger.exception("Unexpected Surfer MCP failure")
        return _json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
    if payload is None:
        payload = {}
    return _json({"ok": True, **payload})


@mcp.tool()
async def surfer_status() -> str:
    """Report Surfer availability, version, visibility, workspace and open document count."""
    return await _call(session.status)


@mcp.tool()
async def list_documents() -> str:
    """List the documents currently open in Surfer with their index, name, path and saved state."""
    return await _call(session.list_documents)


@mcp.tool()
async def set_surfer_visible(visible: bool = True) -> str:
    """Show or hide the Surfer application window. Surfer starts automatically if needed."""
    return await _call(lambda: session.set_visible(visible))


@mcp.tool()
async def create_grid(
    data_file: str,
    output_grid: str | None = None,
    x_col: int = 1,
    y_col: int = 2,
    z_col: int = 3,
    algorithm: Algorithm = "kriging",
    cols: int = 300,
    rows: int = 300,
) -> str:
    """Interpolate XYZ point data into a binary Surfer grid (.grd).

    Args:
        data_file: CSV, TSV or whitespace text file containing X, Y, Z columns.
        output_grid: Destination .grd path (workspace-relative or absolute). Defaults to grids/<name>.grd.
        x_col: 1-based X column.
        y_col: 1-based Y column.
        z_col: 1-based Z column.
        algorithm: Gridding algorithm; kriging by default.
        cols: Grid columns (10-4000).
        rows: Grid rows (10-4000).
    """
    return await _call(
        lambda: session.create_grid(
            data_file=data_file,
            output_grid=output_grid,
            x_col=x_col,
            y_col=y_col,
            z_col=z_col,
            algorithm=algorithm,
            cols=cols,
            rows=rows,
        )
    )


@mcp.tool()
async def create_contour_map(
    grid_file: str,
    title: str | None = None,
    style: MapStyle = "color",
    output_image: str | None = None,
    save_plot: str | None = None,
) -> str:
    """Create a map from a .grd grid in a new Surfer plot document.

    Args:
        grid_file: Input .grd grid.
        title: Optional map title.
        style: "color" renders a coloured raster with contour lines, "lines" draws plain contours,
            "filled" fills contours (grayscale in Surfer 13).
        output_image: Optional export path; format inferred from extension (png, jpg, pdf, tif, svg, emf).
        save_plot: Optional .srf plot path.
    """
    return await _call(
        lambda: session.create_contour_map(
            grid_file=grid_file,
            title=title,
            style=style,
            output_image=output_image,
            save_plot=save_plot,
        )
    )


@mcp.tool()
async def create_cross_section(
    grid_file: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    title: str = "Cross-section",
    style: MapStyle = "color",
    vertical_exaggeration: float = 1.0,
    x_label: str = "Distance (m)",
    y_label: str = "Elevation (m)",
    output_image: str | None = None,
    save_plot: str | None = None,
    save_profile_data: str | None = None,
) -> str:
    """Create a geological cross-section along a straight line through a grid.

    The plot combines a location map (with the section line) and a profile below it.

    Args:
        grid_file: Input .grd grid.
        start_x: Section start X in map units.
        start_y: Section start Y in map units.
        end_x: Section end X in map units.
        end_y: Section end Y in map units.
        title: Section title, e.g. "A-A'".
        style: Map style behind the section: "color", "lines" or "filled".
        vertical_exaggeration: Vertical scale factor (1.0 = true scale).
        x_label: Horizontal axis label.
        y_label: Vertical axis label.
        output_image: Optional export path (png, jpg, pdf, tif, svg, emf).
        save_plot: Optional .srf plot path.
        save_profile_data: Optional tab-delimited .dat path for the sampled profile values.
    """
    return await _call(
        lambda: session.create_cross_section(
            grid_file=grid_file,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            title=title,
            style=style,
            vertical_exaggeration=vertical_exaggeration,
            x_label=x_label,
            y_label=y_label,
            output_image=output_image,
            save_plot=save_plot,
            save_profile_data=save_profile_data,
        )
    )


@mcp.tool()
async def create_surface_map(
    grid_file: str,
    title: str | None = None,
    output_image: str | None = None,
    save_plot: str | None = None,
) -> str:
    """Create a 3D surface view from a .grd grid."""
    return await _call(
        lambda: session.create_surface_map(
            grid_file=grid_file,
            title=title,
            output_image=output_image,
            save_plot=save_plot,
        )
    )


@mcp.tool()
async def export_document(output_file: str, document: str = "active") -> str:
    """Export an open Surfer document to png, jpg, pdf, tif, svg or emf.

    Args:
        output_file: Destination path; the extension selects the export filter.
        document: Document name, 1-based index, or "active".
    """
    return await _call(lambda: session.export_document(document, output_file))


@mcp.tool()
async def save_plot(output_file: str, document: str = "active") -> str:
    """Save an open Surfer document as a .srf plot file."""
    return await _call(lambda: session.save_plot(document, output_file))


@mcp.tool()
async def close_document(document: str = "active", save: bool = False) -> str:
    """Close an open Surfer document, optionally saving it first."""
    return await _call(lambda: session.close_document(document, save))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


__all__ = ["mcp", "main"]
