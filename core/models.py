# -*- coding: utf-8 -*-
"""
TOFPA domain models.

Dataclasses that encode the surface-geometry and obstacle-analysis contracts
at the boundary between the QGIS UI layer and the calculation core.

Applying the *type-first* principle (python-best-practices skill): every
public function that deals with TOFPA parameters accepts one of these
dataclasses rather than a sprawling positional argument list.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional


class RunwayDirection(IntEnum):
    """Takeoff direction along the runway polyline."""
    START_TO_END = 0   # s = 0  — takeoff toward the far end of the digitised line
    END_TO_START = -1  # s = -1 — takeoff from the far end back to the start


@dataclass
class TofpaParams:
    """
    Surface geometry and export parameters for a single TOFPA AOC Type A calculation.

    Field descriptions reference ICAO Doc 8168, Vol I, §3.1.3.
    """

    # Surface geometry
    width_tofpa: float          # initial half-width at DER (metres)
    max_width_tofpa: float      # maximum half-width at full divergence (metres)
    cwy_length: float           # clearway length (metres; 0 = no clearway)
    z0: float                   # threshold elevation (metres MSL)
    ze: float                   # end-of-runway elevation (metres MSL)
    s: int                      # RunwayDirection: 0 = start→end, -1 = end→start

    # Layer references
    runway_layer_id: Optional[str]
    threshold_layer_id: Optional[str]
    use_selected_feature: bool

    # Export flags
    export_kmz: bool
    export_aixm: bool

    @classmethod
    def from_dict(cls, d: dict) -> "TofpaParams":
        """Build from the dict returned by ``TofpaDockWidget.get_parameters()``."""
        return cls(
            width_tofpa=float(d["width_tofpa"]),
            max_width_tofpa=float(d["max_width_tofpa"]),
            cwy_length=float(d["cwy_length"]),
            z0=float(d["z0"]),
            ze=float(d["ze"]),
            s=int(d["s"]),
            runway_layer_id=d.get("runway_layer_id"),
            threshold_layer_id=d.get("threshold_layer_id"),
            use_selected_feature=bool(d.get("use_selected_feature", True)),
            export_kmz=bool(d.get("export_kmz", False)),
            export_aixm=bool(d.get("export_aixm", False)),
        )


@dataclass
class ObstacleParams:
    """Obstacle analysis parameters extracted from the TOFPA panel."""

    include_obstacles: bool
    obstacles_layer_id: Optional[str]
    obstacle_height_field: Optional[str]
    obstacle_buffer: float       # horizontal safety buffer around each obstacle (metres)
    min_obstacle_height: float   # minimum height threshold — shorter obstacles are ignored
    enable_shadow_analysis: bool
    shadow_tolerance: float      # angular cone (degrees) within which shadowing can occur

    @classmethod
    def from_dict(cls, d: dict) -> "ObstacleParams":
        """Build from the dict returned by ``TofpaDockWidget.get_parameters()``."""
        return cls(
            include_obstacles=bool(d.get("include_obstacles", False)),
            obstacles_layer_id=d.get("obstacles_layer_id"),
            obstacle_height_field=d.get("obstacle_height_field"),
            obstacle_buffer=float(d.get("obstacle_buffer", 10.0)),
            min_obstacle_height=float(d.get("min_obstacle_height", 5.0)),
            enable_shadow_analysis=bool(d.get("enable_shadow_analysis", False)),
            shadow_tolerance=float(d.get("shadow_tolerance", 5.0)),
        )
