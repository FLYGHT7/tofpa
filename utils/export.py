# -*- coding: utf-8 -*-
"""
TOFPA export utilities: AIXM 5.1.1 XML generation.

These are pure file-operation helpers with no dependency on ``QgsInterface``.
The TOFPA plugin class calls ``generate_aixm_file`` and handles errors /
message-bar notifications itself.
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsProject,
    QgsWkbTypes,
)
from .compat import WKB_POLYGON_GEOM, WKB_LINE_GEOM  # MIGA-02


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_aixm_file(layers: list, file_path: str) -> None:
    """
    Write an AIXM 5.1.1 XML file containing all *layers*.

    Raises on any I/O or XML error — caller must handle.
    """
    root = ET.Element("aixm:AIXMBasicMessage")
    root.set("xmlns:aixm", "http://www.aixm.aero/schema/5.1.1")
    root.set("xmlns:gml", "http://www.opengis.net/gml/3.2")
    root.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set(
        "xsi:schemaLocation",
        "http://www.aixm.aero/schema/5.1.1 "
        "http://www.aixm.aero/schema/5.1.1/AIXM_BasicMessage.xsd",
    )

    header = ET.SubElement(root, "gml:boundedBy")
    ET.SubElement(header, "gml:Null").text = "unknown"

    for layer in layers:
        if layer.featureCount() == 0:
            continue
        if "reference_line" in layer.name().lower():
            _add_reference_line(root, layer)
        else:
            _add_surface(root, layer)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Feature-level helpers
# ---------------------------------------------------------------------------

def _add_surface(root: ET.Element, layer) -> None:
    """Add each feature of *layer* as an AIXM ``NavigationArea``."""
    for feature in layer.getFeatures():
        fm = ET.SubElement(root, "gml:featureMember")
        nav_area = ET.SubElement(fm, "aixm:NavigationArea")
        nav_area.set("gml:id", f"tofpa_surface_{uuid.uuid4().hex[:8]}")

        ts_elem = ET.SubElement(nav_area, "aixm:timeSlice")
        nav_ts = ET.SubElement(ts_elem, "aixm:NavigationAreaTimeSlice")
        nav_ts.set("gml:id", f"ts_{uuid.uuid4().hex[:8]}")

        valid_time = ET.SubElement(nav_ts, "gml:validTime")
        time_period = ET.SubElement(valid_time, "gml:TimePeriod")
        time_period.set("gml:id", f"tp_{uuid.uuid4().hex[:8]}")
        ET.SubElement(time_period, "gml:beginPosition").text = (
            datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        end_pos = ET.SubElement(time_period, "gml:endPosition")
        end_pos.set("indeterminatePosition", "unknown")

        ET.SubElement(nav_ts, "aixm:interpretation").text = "BASELINE"
        ET.SubElement(nav_ts, "aixm:designator").text = "TOFPA_AOC_TypeA"
        ET.SubElement(nav_ts, "aixm:type").text = "TAKEOFF_CLIMB_SURFACE"

        geom = feature.geometry()
        if geom and not geom.isEmpty():
            _add_geometry(nav_ts, geom)


def _add_reference_line(root: ET.Element, layer) -> None:
    """Add each feature of *layer* as an AIXM ``Curve``."""
    for feature in layer.getFeatures():
        fm = ET.SubElement(root, "gml:featureMember")
        curve = ET.SubElement(fm, "aixm:Curve")
        curve.set("gml:id", f"reference_line_{uuid.uuid4().hex[:8]}")
        ET.SubElement(curve, "aixm:designator").text = "TOFPA_REFERENCE_LINE"

        geom = feature.geometry()
        if geom and not geom.isEmpty():
            _add_geometry(curve, geom)


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _add_geometry(parent: ET.Element, geometry) -> None:
    """Transform *geometry* to WGS-84 and attach GML representation."""
    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
    transform = QgsCoordinateTransform(
        geometry.crs() if hasattr(geometry, "crs") else QgsProject.instance().crs(),
        crs_4326,
        QgsProject.instance(),
    )
    geom_4326 = QgsGeometry(geometry)
    geom_4326.transform(transform)

    if geometry.type() == WKB_POLYGON_GEOM:
        _add_gml_surface(parent, geom_4326)
    elif geometry.type() == WKB_LINE_GEOM:
        _add_gml_curve(parent, geom_4326)


def _add_gml_surface(parent: ET.Element, geometry) -> None:
    """Attach a ``gml:Surface`` (polygon) to *parent*."""
    wrapper = ET.SubElement(parent, "aixm:geometryComponent")
    surface = ET.SubElement(wrapper, "aixm:Surface")
    surface.set("gml:id", f"srf_{hash(str(geometry.asWkt())) & 0x7FFFFFFF}")
    surface.set("srsName", "urn:ogc:def:crs:EPSG::4326")
    surface.set("srsDimension", "3")

    patches = ET.SubElement(surface, "gml:patches")
    polygon_patch = ET.SubElement(patches, "gml:PolygonPatch")
    exterior = ET.SubElement(polygon_patch, "gml:exterior")
    linear_ring = ET.SubElement(exterior, "gml:LinearRing")
    pos_list = ET.SubElement(linear_ring, "gml:posList")

    polygon = (
        geometry.asMultiPolygon()[0][0] if geometry.isMultipart()
        else geometry.asPolygon()[0]
    )
    coords: list[str] = []
    for point in polygon:
        coords += [
            f"{point.y():.8f}",
            f"{point.x():.8f}",
            f"{point.z():.3f}" if point.is3D() else "0.000",
        ]
    pos_list.text = " ".join(coords)


def _add_gml_curve(parent: ET.Element, geometry) -> None:
    """Attach a ``gml:Curve`` (linestring) to *parent*."""
    wrapper = ET.SubElement(parent, "aixm:geometryComponent")
    curve = ET.SubElement(wrapper, "aixm:Curve")
    curve.set("gml:id", f"crv_{hash(str(geometry.asWkt())) & 0x7FFFFFFF}")
    curve.set("srsName", "urn:ogc:def:crs:EPSG::4326")
    curve.set("srsDimension", "3")

    segments = ET.SubElement(curve, "gml:segments")
    line_segment = ET.SubElement(segments, "gml:LineStringSegment")
    pos_list = ET.SubElement(line_segment, "gml:posList")

    line = (
        geometry.asMultiPolyline()[0] if geometry.isMultipart()
        else geometry.asPolyline()
    )
    coords: list[str] = []
    for point in line:
        coords += [
            f"{point.y():.8f}",
            f"{point.x():.8f}",
            f"{point.z():.3f}" if point.is3D() else "0.000",
        ]
    pos_list.text = " ".join(coords)
