"""
utils/compat.py — Capa de compatibilidad para QGIS 3.x (PyQt5) y QGIS 4.0 (PyQt6).

QGIS 4.0 (6 de marzo de 2026) introduce PyQt6 con los siguientes cambios importantes:
  - Clase QVariant eliminada  → reemplazada por QMetaType.Type
  - Scoping de enums: QgsWkbTypes.PolygonGeometry → QgsWkbTypes.GeometryType.PolygonGeometry
  - QgsMapLayerProxyModel.VectorLayer → QgsMapLayerProxyModel.Filter.VectorLayer

Este módulo expone constantes que funcionan en ambas versiones de Qt,
detectando en tiempo de ejecución qué API está disponible.

Uso::

    from .utils.compat import FIELD_INT, FIELD_DOUBLE, FIELD_STRING
    from .utils.compat import WKB_POLYGON_GEOM, WKB_LINE_GEOM, WKB_POINT_GEOM
    from .utils.compat import LAYER_FILTER_VECTOR

Referencias:
    - https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html
    - https://api.qgis.org/api/api_break.html
    - Tarea MIGA-01..MIGA-06 en REFACTORING_PLAN.md
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# MIGA-01: Constantes de tipo de campo (QVariant en PyQt5 → QMetaType en PyQt6)
# ---------------------------------------------------------------------------
try:
    from qgis.PyQt.QtCore import QMetaType  # PyQt6 / Qt 6

    FIELD_INT: int = QMetaType.Type.Int       # type: ignore[attr-defined]
    FIELD_DOUBLE: int = QMetaType.Type.Double  # type: ignore[attr-defined]
    FIELD_STRING: int = QMetaType.Type.QString  # type: ignore[attr-defined]
except (ImportError, AttributeError):
    from qgis.PyQt.QtCore import QVariant  # type: ignore[attr-defined]  # PyQt5 / Qt 5

    FIELD_INT: int = QVariant.Int      # type: ignore[assignment]
    FIELD_DOUBLE: int = QVariant.Double  # type: ignore[assignment]
    FIELD_STRING: int = QVariant.String  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# MIGA-02: Constantes de geometría WKB y filtro de capas
#           (enums sin scope en PyQt5 → enums con scope en PyQt6)
# ---------------------------------------------------------------------------
from qgis.core import QgsWkbTypes, QgsMapLayerProxyModel  # noqa: E402
from qgis.PyQt.QtCore import Qt  # noqa: E402

try:
    # QGIS 4.0 / PyQt6: acceso con scope completo de enum
    WKB_POLYGON_GEOM: int = QgsWkbTypes.GeometryType.PolygonGeometry  # type: ignore[attr-defined]
    WKB_LINE_GEOM: int = QgsWkbTypes.GeometryType.LineGeometry        # type: ignore[attr-defined]
    WKB_POINT_GEOM: int = QgsWkbTypes.GeometryType.PointGeometry      # type: ignore[attr-defined]
    LAYER_FILTER_VECTOR: int = QgsMapLayerProxyModel.Filter.VectorLayer  # type: ignore[attr-defined]
except AttributeError:
    # QGIS 3.x / PyQt5: acceso sin scope
    WKB_POLYGON_GEOM: int = QgsWkbTypes.PolygonGeometry         # type: ignore[assignment, attr-defined]
    WKB_LINE_GEOM: int = QgsWkbTypes.LineGeometry               # type: ignore[assignment, attr-defined]
    WKB_POINT_GEOM: int = QgsWkbTypes.PointGeometry             # type: ignore[assignment, attr-defined]
    LAYER_FILTER_VECTOR: int = QgsMapLayerProxyModel.VectorLayer  # type: ignore[assignment, attr-defined]

# ---------------------------------------------------------------------------
# MIGA-05: Constantes de flags de Qt
#           (sin scope en PyQt5 → con scope enum en PyQt6)
# ---------------------------------------------------------------------------
try:
    # QGIS 4.0 / PyQt6: acceso con scope completo de DockWidgetArea
    DOCK_RIGHT = Qt.DockWidgetArea.RightDockWidgetArea  # type: ignore[attr-defined]
except AttributeError:
    # QGIS 3.x / PyQt5: acceso sin scope
    DOCK_RIGHT = Qt.RightDockWidgetArea  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# MIGA-03: exec_() → exec()  (PyQt6 eliminó el alias con guión bajo)
# Este cambio se aplica directamente en el código de cada diálogo/loop,
# pero se documenta aquí como referencia central.
# Patrón de búsqueda: \.exec_\(\)
# Patrón de reemplazo: .exec()
# ---------------------------------------------------------------------------

__all__ = [
    # Tipos de campo
    "FIELD_INT",
    "FIELD_DOUBLE",
    "FIELD_STRING",
    # Tipos de geometría WKB
    "WKB_POLYGON_GEOM",
    "WKB_LINE_GEOM",
    "WKB_POINT_GEOM",
    # Filtro de capa
    "LAYER_FILTER_VECTOR",
    # Flags de Qt
    "DOCK_RIGHT",
]
