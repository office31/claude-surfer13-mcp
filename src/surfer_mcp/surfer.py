from __future__ import annotations

import asyncio
import csv
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

try:
    import pythoncom
    import pywintypes
    import win32com.client as win32
    from win32com.client import dynamic

    _COM_IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - only on non-Windows
    _COM_IMPORT_ERROR = exc
    pythoncom = pywintypes = win32 = dynamic = None  # type: ignore[assignment]

PROGID = "Surfer.Application"

DOC_PLOT = 1
PAGE_LANDSCAPE = 2
GRID_BINARY = 1

GRID_ALGORITHMS = {
    "idw": 1,
    "kriging": 2,
    "min_curvature": 3,
    "shepards": 4,
    "natural_neighbor": 5,
    "nearest_neighbor": 6,
    "regression": 7,
    "radial_basis": 8,
    "triangulation": 9,
    "moving_average": 10,
    "data_metrics": 11,
    "local_polynomial": 12,
}

EXPORT_FILTERS = {
    ".png": "png",
    ".jpg": "jpg",
    ".jpeg": "jpg",
    ".pdf": "pdfv",
    ".tif": "tif",
    ".tiff": "tif",
    ".svg": "svg",
    ".emf": "emf",
}


class SurferError(RuntimeError):
    """Raised when Surfer or its automation interface cannot complete an action."""


def default_workspace() -> Path:
    env = os.environ.get("SURFER_MCP_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    documents = Path.home() / "Documents"
    base = documents if documents.is_dir() else Path.home()
    return (base / "SurferMCP").resolve()


def normalize_xyz(source: Path, required_columns: int) -> tuple[Path, int]:
    """Rewrite point data as whitespace-separated numeric columns, as Surfer requires."""
    lines = []
    with source.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            line = raw.strip()
            if line and not line.startswith("#"):
                lines.append(line)
    if not lines:
        raise SurferError(f"Data file is empty: {source}")

    first = lines[0]
    delimiter = ","
    if ";" in first and "," not in first:
        delimiter = ";"
    elif "\t" in first and "," not in first:
        delimiter = "\t"
    elif "," not in first and ";" not in first and "\t" not in first:
        delimiter = None

    rows: list[list[float]] = []
    for line in lines:
        cells = line.split() if delimiter is None else next(csv.reader([line], delimiter=delimiter))
        cells = [cell.strip() for cell in cells]
        if len(cells) < required_columns:
            continue
        try:
            rows.append([float(cell) for cell in cells])
        except ValueError:
            continue
    if len(rows) < 4:
        raise SurferError(
            f"Not enough numeric rows in {source} (found {len(rows)}, need at least 4). "
            "Expected XYZ columns; headers are ignored."
        )

    handle, temp_name = tempfile.mkstemp(prefix="surfer_mcp_", suffix=".txt")
    temp_path = Path(temp_name)
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
        for values in rows:
            out.write(" ".join(f"{value:.10g}" for value in values) + "\n")
    return temp_path, len(rows)


class SurferSession:
    def __init__(self, workspace: str | Path | None = None, visible: bool | None = None):
        self.workspace = Path(workspace).expanduser().resolve() if workspace else default_workspace()
        if visible is None:
            visible = os.environ.get("SURFER_MCP_VISIBLE", "1").strip().lower() not in {
                "0",
                "false",
                "no",
                "off",
            }
        self.visible = visible
        self._app: Any = None
        self._owned = False
        self._lock = asyncio.Lock()

    async def run(self, action: Callable[[], Any]) -> Any:
        async with self._lock:
            try:
                return action()
            except SurferError:
                raise
            except Exception as exc:
                if _COM_IMPORT_ERROR is None and isinstance(exc, pywintypes.com_error):
                    raise SurferError(_com_error_text(exc)) from exc
                raise

    def _ensure_app(self):
        if self._app is not None:
            return self._app
        if _COM_IMPORT_ERROR is not None:
            raise SurferError(
                "pywin32 is required to drive Surfer. Install it with: pip install pywin32 (Windows only)."
            )
        pythoncom.CoInitialize()
        preexisting = True
        try:
            win32.GetActiveObject(PROGID)
        except Exception:
            preexisting = False
        try:
            app = win32.gencache.EnsureDispatch(PROGID)
        except Exception as exc:
            try:
                app = win32.Dispatch(PROGID)
            except Exception:
                raise SurferError(
                    "Golden Software Surfer could not be started. Install Surfer 13 or newer "
                    "and check that its COM automation interface is registered."
                ) from exc
        if not preexisting:
            self._owned = True
            try:
                app.Visible = self.visible
            except Exception:
                pass
        self._app = app
        return app

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "workspace": str(self.workspace),
            "visible_preference": self.visible,
            "com_available": _COM_IMPORT_ERROR is None,
        }
        if _COM_IMPORT_ERROR is not None:
            info["error"] = f"pywin32 import failed: {_COM_IMPORT_ERROR}"
            return info
        try:
            app = win32.GetActiveObject(PROGID)
        except Exception:
            info["running"] = False
            info["note"] = "Surfer is not running yet; it will start on the first tool call."
            return info
        info.update(
            running=True,
            version=str(app.Version),
            visible=bool(app.Visible),
            documents=app.Documents.Count,
        )
        return info

    def list_documents(self) -> dict[str, Any]:
        app = self._ensure_app()
        documents = []
        for index in range(1, app.Documents.Count + 1):
            doc = app.Documents.Item(index)
            documents.append(
                {
                    "index": index,
                    "name": doc.Name,
                    "full_name": str(doc.FullName),
                    "saved": bool(doc.Saved),
                }
            )
        return {"count": len(documents), "documents": documents}

    def set_visible(self, visible: bool) -> dict[str, Any]:
        app = self._ensure_app()
        app.Visible = bool(visible)
        self.visible = bool(visible)
        return {"visible": bool(app.Visible)}

    def create_grid(
        self,
        data_file: str,
        output_grid: str | None = None,
        x_col: int = 1,
        y_col: int = 2,
        z_col: int = 3,
        algorithm: str = "kriging",
        cols: int = 300,
        rows: int = 300,
    ) -> dict[str, Any]:
        for name, value in (("x_col", x_col), ("y_col", y_col), ("z_col", z_col)):
            if not isinstance(value, int) or value < 1:
                raise SurferError(f"{name} must be a positive 1-based column index.")
        if not 10 <= cols <= 4000 or not 10 <= rows <= 4000:
            raise SurferError("cols and rows must be between 10 and 4000.")
        algorithm_key = algorithm.strip().lower()
        algorithm_id = GRID_ALGORITHMS.get(algorithm_key)
        if algorithm_id is None:
            raise SurferError(
                f"Unknown algorithm '{algorithm}'. Choose one of: {', '.join(sorted(GRID_ALGORITHMS))}."
            )

        source = self._resolve_input(data_file)
        output = self._resolve_output(output_grid, f"grids/{source.stem}.grd")
        if output.suffix.lower() != ".grd":
            raise SurferError("The output grid must use the .grd extension.")

        app = self._ensure_app()
        temp_data, row_count = normalize_xyz(source, max(x_col, y_col, z_col))
        started = time.perf_counter()
        try:
            app.ScreenUpdating = False
        except Exception:
            pass
        try:
            app.GridData(
                DataFile=str(temp_data),
                xCol=x_col,
                yCol=y_col,
                zCol=z_col,
                NumCols=cols,
                NumRows=rows,
                Algorithm=algorithm_id,
                ShowReport=False,
                OutGrid=str(output),
                OutFmt=GRID_BINARY,
            )
        finally:
            temp_data.unlink(missing_ok=True)
            try:
                app.ScreenUpdating = True
            except Exception:
                pass

        if not output.is_file() or output.stat().st_size == 0:
            raise SurferError("Surfer did not create the output grid.")
        return {
            "grid_file": str(output),
            "size_bytes": output.stat().st_size,
            "source": str(source),
            "points": row_count,
            "columns": {"x": x_col, "y": y_col, "z": z_col},
            "algorithm": algorithm_key,
            "grid_size": {"cols": cols, "rows": rows},
            "elapsed_seconds": round(time.perf_counter() - started, 2),
        }

    def create_contour_map(
        self,
        grid_file: str,
        title: str | None = None,
        style: str = "color",
        output_image: str | None = None,
        save_plot: str | None = None,
    ) -> dict[str, Any]:
        grid = self._resolve_input(grid_file, {".grd"})
        style = _validate_style(style)
        doc = self._new_plot()
        self._add_map(doc, grid, style)
        self._add_title(doc, title)
        result: dict[str, Any] = {
            "grid_file": str(grid),
            "style": style,
        }
        if output_image:
            result["image"] = self._export(doc, output_image)
        if save_plot:
            result["plot_file"] = self._save_plot(doc, save_plot)
        result["document"] = doc.Name
        return result

    def create_cross_section(
        self,
        grid_file: str,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        title: str = "Cross-section",
        style: str = "color",
        vertical_exaggeration: float = 1.0,
        x_label: str = "Distance (m)",
        y_label: str = "Elevation (m)",
        output_image: str | None = None,
        save_plot: str | None = None,
        save_profile_data: str | None = None,
    ) -> dict[str, Any]:
        grid = self._resolve_input(grid_file, {".grd"})
        style = _validate_style(style)
        if (float(start_x), float(start_y)) == (float(end_x), float(end_y)):
            raise SurferError("Section start and end points must be different.")
        if not 0.1 <= vertical_exaggeration <= 100:
            raise SurferError("vertical_exaggeration must be between 0.1 and 100.")

        doc = self._new_plot()
        frame = self._add_map(doc, grid, style)
        profile = dynamic.Dispatch(
            dynamic.Dispatch(frame).Profiles.Add(
                [float(start_x), float(start_y), float(end_x), float(end_y)]
            )
        )
        profile.TitleText = title
        profile.Axes.Item("X Axis").Title = x_label
        profile.Axes.Item("Y Axis").Title = y_label
        profile.yMapPerPU = profile.xMapPerPU / float(vertical_exaggeration)

        result: dict[str, Any] = {
            "grid_file": str(grid),
            "style": style,
            "line": {"start": [start_x, start_y], "end": [end_x, end_y]},
            "vertical_exaggeration": vertical_exaggeration,
        }
        if output_image:
            result["image"] = self._export(doc, output_image)
        if save_plot:
            result["plot_file"] = self._save_plot(doc, save_plot)
        if save_profile_data:
            data_path = self._resolve_output(save_profile_data, None)
            profile.SaveDataFile(FileName=str(data_path))
            if not data_path.is_file():
                raise SurferError("Surfer did not create the profile data file.")
            result["profile_data"] = self._file_info(data_path)
        result["document"] = doc.Name
        return result

    def create_surface_map(
        self,
        grid_file: str,
        title: str | None = None,
        output_image: str | None = None,
        save_plot: str | None = None,
    ) -> dict[str, Any]:
        grid = self._resolve_input(grid_file, {".grd"})
        doc = self._new_plot()
        doc.Shapes.AddSurface(str(grid))
        self._add_title(doc, title)
        result: dict[str, Any] = {"grid_file": str(grid)}
        if output_image:
            result["image"] = self._export(doc, output_image)
        if save_plot:
            result["plot_file"] = self._save_plot(doc, save_plot)
        result["document"] = doc.Name
        return result

    def export_document(self, document: str, output_file: str) -> dict[str, Any]:
        doc = self._find_document(document)
        return self._export(doc, output_file)

    def save_plot(self, document: str, output_file: str) -> dict[str, Any]:
        doc = self._find_document(document)
        return self._save_plot(doc, output_file)

    def close_document(self, document: str, save: bool = False) -> dict[str, Any]:
        doc = self._find_document(document)
        name = doc.Name
        if save:
            doc.Save()
        doc.Close()
        return {"closed": name}

    def quit(self) -> None:
        if self._app is not None and self._owned:
            self._app.Quit()
        self._app = None
        self._owned = False

    def _new_plot(self):
        app = self._ensure_app()
        doc = app.Documents.Add(DOC_PLOT)
        try:
            doc.PageSetup.Orientation = PAGE_LANDSCAPE
        except Exception:
            pass
        return doc

    def _add_map(self, doc, grid: Path, style: str):
        if style == "color":
            frame = doc.Shapes.AddImageMap(str(grid))
            dynamic.Dispatch(doc.Shapes).AddContourLayer(Map=frame, GridFileName=str(grid))
            return frame
        frame = doc.Shapes.AddContourMap(str(grid))
        if style == "filled":
            dynamic.Dispatch(frame.Overlays(1)).FillContours = True
        return frame

    def _add_title(self, doc, title: str | None) -> None:
        if not title:
            return
        text = doc.Shapes.AddText(X=0.7, Y=7.8, Text=title)
        text.Font.Size = 16
        text.Font.Bold = True

    def _export(self, doc, output_file: str) -> dict[str, Any]:
        output = self._resolve_output(output_file, None)
        filter_id = EXPORT_FILTERS.get(output.suffix.lower())
        if filter_id is None:
            supported = ", ".join(sorted(EXPORT_FILTERS))
            raise SurferError(f"Unsupported export format '{output.suffix}'. Use: {supported}.")
        doc.Export2(FileName=str(output), FilterId=filter_id)
        if not output.is_file() or output.stat().st_size == 0:
            raise SurferError("Surfer did not create the exported file.")
        return self._file_info(output)

    def _save_plot(self, doc, output_file: str) -> dict[str, Any]:
        output = self._resolve_output(output_file, None)
        if output.suffix.lower() != ".srf":
            raise SurferError("Surfer plot files must use the .srf extension.")
        doc.SaveAs(FileName=str(output))
        if not output.is_file():
            raise SurferError("Surfer did not create the plot file.")
        return {"document": doc.Name, **self._file_info(output)}

    def _find_document(self, identifier: str):
        app = self._ensure_app()
        value = (identifier or "active").strip()
        if value.lower() in {"", "active"}:
            doc = app.ActiveDocument
            if doc is None:
                raise SurferError("No active Surfer document.")
            return doc
        if value.isdigit():
            index = int(value)
            if not 1 <= index <= app.Documents.Count:
                raise SurferError(f"Document index {index} is out of range (1..{app.Documents.Count}).")
            return app.Documents.Item(index)
        for index in range(1, app.Documents.Count + 1):
            doc = app.Documents.Item(index)
            if value.lower() in {str(doc.Name).lower(), str(doc.FullName).lower()}:
                return doc
        names = ", ".join(str(app.Documents.Item(i).Name) for i in range(1, app.Documents.Count + 1))
        raise SurferError(f"Document '{identifier}' not found. Open documents: {names or 'none'}.")

    def _resolve_input(self, value: str, suffixes: set[str] | None = None) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.workspace / path
        path = path.resolve()
        if not path.is_file():
            raise SurferError(f"Input file not found: {path}")
        if suffixes and path.suffix.lower() not in suffixes:
            expected = ", ".join(sorted(suffixes))
            raise SurferError(f"Expected a {expected} file, got: {path.name}")
        return path

    def _resolve_output(self, value: str | None, default_relative: str | None) -> Path:
        if value:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = self.workspace / path
            path = path.resolve()
            if not path.parent.is_dir():
                if path.is_relative_to(self.workspace):
                    path.parent.mkdir(parents=True, exist_ok=True)
                else:
                    raise SurferError(f"Output directory does not exist: {path.parent}")
            return path
        if not default_relative:
            raise SurferError("An output path is required.")
        path = (self.workspace / default_relative).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _file_info(path: Path) -> dict[str, Any]:
        return {"path": str(path), "size_bytes": path.stat().st_size}


def _validate_style(style: str) -> str:
    value = (style or "color").strip().lower()
    if value not in {"color", "lines", "filled"}:
        raise SurferError("style must be 'color', 'lines' or 'filled'.")
    return value


def _com_error_text(error: Exception) -> str:
    info = getattr(error, "excepinfo", None)
    if info and len(info) > 2 and info[2]:
        return str(info[2]).strip()
    return str(error).strip() or "Unknown Surfer automation error."
