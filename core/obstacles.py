# -*- coding: utf-8 -*-
"""
TOFPA obstacle analysis.

All obstacle processing and shadow-analysis logic extracted from the
monolithic TOFPA class so it can be tested and reused independently.

``ObstacleAnalyzer`` has no dependency on ``QgsInterface`` (no message-bar
calls). Errors are communicated via exceptions; the TOFPA plugin class
catches them and shows them via the QGIS message bar.
"""

from __future__ import annotations

import logging
from math import atan, atan2, pi
from typing import Any, Optional

from qgis.core import (
    QgsFillSymbol,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsMarkerSymbol,
    QgsPoint,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from ..utils.compat import FIELD_INT, FIELD_DOUBLE, FIELD_STRING, WKB_POLYGON_GEOM  # MIGA-01, MIGA-02

logger = logging.getLogger("TOFPA.obstacles")


class ObstacleAnalyzer:
    """
    Pure obstacle / shadow-analysis operations.

    Instantiate once per calculation run:

        analyzer = ObstacleAnalyzer()
        layers_info = analyzer.create_layers(crs)
        ...
        analyzer.finalize_layers(layers_info)
    """

    # ------------------------------------------------------------------
    # Layer creation
    # ------------------------------------------------------------------

    def create_layers(self, crs) -> dict:
        """Create memory layers for obstacles analysis including shadow analysis layers."""
        critical_fields = [
            QgsField("id", FIELD_INT),
            QgsField("height", FIELD_DOUBLE),
            QgsField("buffer_m", FIELD_DOUBLE),
            QgsField("status", FIELD_STRING),
            QgsField("intersection", FIELD_STRING),
            QgsField("shadow_status", FIELD_STRING),
            QgsField("shadowed_by", FIELD_STRING),
        ]

        def _make_point_layer(name: str) -> QgsVectorLayer:
            layer = QgsVectorLayer(f"PointZ?crs={crs.authid()}", name, "memory")
            layer.dataProvider().addAttributes(critical_fields)
            layer.updateFields()
            return layer

        shadowed_layer = _make_point_layer("Shadowed_Obstacles")
        visible_layer = _make_point_layer("Visible_Critical_Obstacles")
        critical_layer = _make_point_layer("Critical_Obstacles")
        safe_layer = _make_point_layer("Safe_Obstacles")

        buffer_layer = QgsVectorLayer(f"PolygonZ?crs={crs.authid()}", "Obstacle_Buffers", "memory")
        buffer_fields = [
            QgsField("obstacle_id", FIELD_INT),
            QgsField("buffer_m", FIELD_DOUBLE),
            QgsField("status", FIELD_STRING),
        ]
        buffer_layer.dataProvider().addAttributes(buffer_fields)
        buffer_layer.updateFields()

        return {
            "critical_layer": critical_layer,
            "safe_layer": safe_layer,
            "shadowed_layer": shadowed_layer,
            "visible_layer": visible_layer,
            "buffer_layer": buffer_layer,
        }

    # ------------------------------------------------------------------
    # Single-obstacle analysis
    # ------------------------------------------------------------------

    def analyze_single(
        self,
        feature,
        height_field: Optional[str],
        buffer_distance: float,
        min_height: float,
        tofpa_surface_layer,
        layers_info: dict,
    ) -> dict:
        """Analyze a single obstacle against the TOFPA surface.

        Returns a dict with keys: ``is_critical``, ``height``,
        ``intersection_type``, ``obstacle_point``.

        Raises ``ValueError`` for features with invalid geometry.
        """
        geom = feature.geometry()
        if not geom or geom.isEmpty():
            raise ValueError("Invalid geometry")

        # Resolve obstacle height
        obstacle_height = min_height
        if height_field:
            height_value = feature.attribute(height_field)
            if height_value is not None and isinstance(height_value, (int, float)):
                obstacle_height = max(float(height_value), min_height)

        # Build 3-D obstacle point
        if geom.type() == WKB_POLYGON_GEOM:
            centroid = geom.centroid().asPoint()
            obstacle_point = QgsPoint(centroid.x(), centroid.y(), obstacle_height)
        else:
            point = geom.asPoint()
            obstacle_point = QgsPoint(point.x(), point.y(), obstacle_height)

        # Buffer (BUG-01 fix: fromPointXY requires QgsPointXY, not QgsPoint)
        buffer_geom = (
            QgsGeometry.fromPointXY(QgsPointXY(obstacle_point.x(), obstacle_point.y()))
            .buffer(buffer_distance, 16)
        )

        # Intersection test
        is_critical = False
        intersection_type = "None"
        for tofpa_feature in tofpa_surface_layer.getFeatures():
            if buffer_geom.intersects(tofpa_feature.geometry()):
                is_critical = True
                intersection_type = "Buffer intersects TOFPA surface"
                break

        # Build obstacle feature (shadow fields populated later)
        obstacle_feature = QgsFeature()
        obstacle_feature.setGeometry(QgsGeometry(obstacle_point))
        obstacle_feature.setAttributes([
            int(feature.id()),
            obstacle_height,
            buffer_distance,
            "CRITICAL" if is_critical else "SAFE",
            intersection_type,
            "",  # shadow_status
            "",  # shadowed_by
        ])

        # Build buffer feature
        buffer_feature = QgsFeature()
        buffer_feature.setGeometry(buffer_geom)
        buffer_feature.setAttributes([int(feature.id()), buffer_distance,
                                      "CRITICAL" if is_critical else "SAFE"])

        if is_critical:
            layers_info["critical_layer"].dataProvider().addFeatures([obstacle_feature])
        else:
            layers_info["safe_layer"].dataProvider().addFeatures([obstacle_feature])
        layers_info["buffer_layer"].dataProvider().addFeatures([buffer_feature])

        return {
            "is_critical": is_critical,
            "height": obstacle_height,
            "intersection_type": intersection_type,
            "obstacle_point": obstacle_point,
        }

    # ------------------------------------------------------------------
    # Shadow analysis
    # ------------------------------------------------------------------

    def perform_shadow_analysis(
        self,
        obstacles_data: list[dict],
        tofpa_surface_layer,
        shadow_tolerance: float = 5.0,
    ) -> dict:
        """
        Determine which critical obstacles are shadowed (hidden) by others.

        Shadow logic:
        1. Locate the takeoff reference point from the TOFPA surface polygon.
        2. For each critical obstacle, check whether any *closer*, *taller*
           obstacle lies within the angular cone (``shadow_tolerance`` degrees).
        3. Confirm the blockage via elevation angles.
        """
        takeoff_point = self.get_takeoff_reference_point(tofpa_surface_layer)
        if not takeoff_point:
            return {"shadowed_obstacles": [], "visible_obstacles": obstacles_data}

        critical_obstacles = [o for o in obstacles_data if o["is_critical"]]
        shadowed_obstacles: list[dict] = []
        visible_obstacles: list[dict] = []

        for obstacle in critical_obstacles:
            is_shadowed, shadowing = self.is_obstacle_shadowed(
                obstacle, critical_obstacles, takeoff_point, shadow_tolerance
            )
            if is_shadowed:
                obstacle["shadow_status"] = "SHADOWED"
                obstacle["shadowed_by"] = f"Obstacle ID {shadowing['feature'].id()}"
                shadowed_obstacles.append(obstacle)
            else:
                obstacle["shadow_status"] = "VISIBLE"
                obstacle["shadowed_by"] = ""
                visible_obstacles.append(obstacle)

        # Non-critical obstacles are always "not applicable"
        for obstacle in obstacles_data:
            if not obstacle["is_critical"]:
                obstacle["shadow_status"] = "NOT_APPLICABLE"
                obstacle["shadowed_by"] = ""
                visible_obstacles.append(obstacle)

        return {
            "shadowed_obstacles": shadowed_obstacles,
            "visible_obstacles": visible_obstacles,
            "takeoff_point": takeoff_point,
        }

    def get_takeoff_reference_point(self, tofpa_surface_layer) -> Optional[QgsPoint]:
        """
        Return the midpoint of the DER (near) edge of the TOFPA surface polygon.

        Vertex order in the surface polygon (as built by create_tofpa_surface):
          idx 0: pt_03DR   idx 1: pt_03DL   idx 2: pt_02DL
          idx 3: pt_01DL   idx 4: pt_01DR   idx 5: pt_02DR   idx 6: close
        The DER start edge is pt_01DL (3) ↔ pt_01DR (4).  — BUG-04 fix.
        """
        try:
            for feature in tofpa_surface_layer.getFeatures():
                geom = feature.geometry()
                if geom.type() == WKB_POLYGON_GEOM:
                    vertices = geom.asPolygon()[0]
                    if len(vertices) >= 6:
                        p1 = vertices[3]  # pt_01DL
                        p2 = vertices[4]  # pt_01DR
                        x = (p1.x() + p2.x()) / 2
                        y = (p1.y() + p2.y()) / 2
                        z = (p1.z() + p2.z()) / 2 if p1.is3D() else 0.0
                        return QgsPoint(x, y, z)
            return None
        except Exception as exc:
            logger.error("Error getting takeoff reference point: %s", exc)
            return None

    def is_obstacle_shadowed(
        self,
        target_obstacle: dict,
        all_obstacles: list[dict],
        takeoff_point: QgsPoint,
        shadow_tolerance: float = 5.0,
    ) -> tuple[bool, Optional[dict]]:
        """
        Return ``(True, shadowing_obstacle)`` if *target_obstacle* is hidden
        behind another obstacle as seen from *takeoff_point*.
        """
        target_point = target_obstacle["point"]
        target_height = target_obstacle["height"]
        target_distance = takeoff_point.distance(target_point)
        target_angle = self.calculate_bearing(takeoff_point, target_point)

        for other in all_obstacles:
            if other["feature"].id() == target_obstacle["feature"].id():
                continue

            other_point = other["point"]
            other_distance = takeoff_point.distance(other_point)
            if other_distance >= target_distance:
                continue
            if other["height"] <= target_height:
                continue

            other_angle = self.calculate_bearing(takeoff_point, other_point)
            diff = abs(target_angle - other_angle)
            if diff > 180:
                diff = 360 - diff
            if diff <= shadow_tolerance:
                if self.check_elevation_shadow(
                    takeoff_point, target_point, target_height,
                    other_point, other["height"]
                ):
                    return True, other

        return False, None

    def calculate_bearing(self, from_point: QgsPoint, to_point: QgsPoint) -> float:
        """Bearing (azimuth, degrees) from *from_point* to *to_point*."""
        try:
            return from_point.azimuth(to_point)
        except Exception:
            dx = to_point.x() - from_point.x()
            dy = to_point.y() - from_point.y()
            return (atan2(dx, dy) * 180 / pi) % 360

    def check_elevation_shadow(
        self,
        takeoff_point: QgsPoint,
        target_point: QgsPoint,
        target_height: float,
        shadow_point: QgsPoint,
        shadow_height: float,
    ) -> bool:
        """
        Return ``True`` if *shadow_point* (at *shadow_height*) blocks the line
        of sight from *takeoff_point* to *target_point* (at *target_height*).
        """
        try:
            target_dist = takeoff_point.distance(target_point)
            shadow_dist = takeoff_point.distance(shadow_point)
            if target_dist <= 0 or shadow_dist <= 0:
                return False

            tof_z = takeoff_point.z() if takeoff_point.is3D() else 0.0
            target_elev = atan((target_height - tof_z) / target_dist) * 180 / pi
            shadow_elev = atan((shadow_height - tof_z) / shadow_dist) * 180 / pi
            return shadow_elev > target_elev

        except Exception as exc:
            logger.error("Error in elevation shadow check: %s", exc)
            return False

    def apply_shadow_results(
        self,
        layers_info: dict,
        shadow_results: dict,
        buffer_distance: float,
    ) -> None:
        """
        Populate the shadowed / visible layers from *shadow_results*.

        BUG-02 fix: ``buffer_distance`` is the user-supplied value, NOT hardcoded 10.0.
        """
        try:
            for obstacle in shadow_results.get("shadowed_obstacles", []):
                if obstacle["is_critical"]:
                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry(obstacle["point"]))
                    feat.setAttributes([
                        int(obstacle["feature"].id()),
                        obstacle["height"],
                        buffer_distance,
                        "CRITICAL",
                        obstacle["obstacle_info"]["intersection_type"],
                        obstacle["shadow_status"],
                        obstacle["shadowed_by"],
                    ])
                    layers_info["shadowed_layer"].dataProvider().addFeatures([feat])

            for obstacle in shadow_results.get("visible_obstacles", []):
                if obstacle["is_critical"]:
                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry(obstacle["point"]))
                    feat.setAttributes([
                        int(obstacle["feature"].id()),
                        obstacle["height"],
                        buffer_distance,
                        "CRITICAL",
                        obstacle["obstacle_info"]["intersection_type"],
                        obstacle.get("shadow_status", "VISIBLE"),
                        obstacle.get("shadowed_by", ""),
                    ])
                    layers_info["visible_layer"].dataProvider().addFeatures([feat])

        except Exception as exc:
            logger.error("Error applying shadow results: %s", exc)

    # ------------------------------------------------------------------
    # Map layer finalisation
    # ------------------------------------------------------------------

    def finalize_layers(self, layers_info: dict) -> None:
        """Apply symbology to each obstacles layer and add them to the QGIS map."""
        _sym = QgsMarkerSymbol.createSimple

        layers_info["critical_layer"].renderer().setSymbol(
            _sym({"color": "255,0,0,255", "size": "4", "outline_color": "0,0,0,255"})
        )
        layers_info["safe_layer"].renderer().setSymbol(
            _sym({"color": "0,255,0,255", "size": "3", "outline_color": "0,0,0,255"})
        )

        if layers_info.get("shadowed_layer") and layers_info["shadowed_layer"].featureCount() > 0:
            layers_info["shadowed_layer"].renderer().setSymbol(
                _sym({"color": "255,165,0,255", "size": "4",
                      "outline_color": "0,0,0,255", "outline_width": "0.5"})
            )
        if layers_info.get("visible_layer") and layers_info["visible_layer"].featureCount() > 0:
            layers_info["visible_layer"].renderer().setSymbol(
                _sym({"color": "139,0,0,255", "size": "5",
                      "outline_color": "0,0,0,255", "outline_width": "0.5"})
            )

        layers_info["buffer_layer"].renderer().setSymbol(
            QgsFillSymbol.createSimple({
                "color": "255,255,0,100",
                "outline_color": "255,165,0,255",
                "outline_width": "0.3",
            })
        )

        layers_to_add = [
            layers_info["critical_layer"],
            layers_info["safe_layer"],
            layers_info["buffer_layer"],
        ]
        if layers_info.get("shadowed_layer") and layers_info["shadowed_layer"].featureCount() > 0:
            layers_to_add.append(layers_info["shadowed_layer"])
        if layers_info.get("visible_layer") and layers_info["visible_layer"].featureCount() > 0:
            layers_to_add.append(layers_info["visible_layer"])

        QgsProject.instance().addMapLayers(layers_to_add)
