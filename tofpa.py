# -*- coding: utf-8 -*-
"""
/***************************************************************************
 FLYGHT7 -  TOFPA
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool

 /***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QAction
from .utils.compat import FIELD_INT, FIELD_STRING, DOCK_RIGHT  # MIGA-01, MIGA-05
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry,
                      QgsPoint, QgsPointXY, QgsField, QgsPolygon, QgsLineString, Qgis,
                      QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem, QgsWkbTypes)

import logging
import os.path

# Import the dockwidget with error handling
try:
    from .tofpa_dockwidget import TofpaDockWidget
except ImportError as e:
    logger.error("Import error: %s", e)
    # Fallback import
    import sys
    import os
    plugin_dir = os.path.dirname(__file__)
    sys.path.insert(0, plugin_dir)
    from tofpa_dockwidget import TofpaDockWidget

# Module logger
logger = logging.getLogger('TOFPA')

# Core modules — imported with relative/absolute fallback for QGIS plugin compatibility
try:
    from .core.models import ObstacleParams, TofpaParams
    from .core.obstacles import ObstacleAnalyzer
    from .utils.export import generate_aixm_file
except ImportError:
    from core.models import ObstacleParams, TofpaParams
    from core.obstacles import ObstacleAnalyzer
    from utils.export import generate_aixm_file

# ---------------------------------------------------------------------------
# ICAO Doc 8168 — TOFPA AOC Type A surface constants
# ---------------------------------------------------------------------------
TOFPA_DIVERGENCE_RATIO: float = 0.125    # 12.5% semi-width divergence per metre forward
TOFPA_CLIMB_GRADIENT: float = 0.012     # 1.2% climb gradient
TOFPA_SURFACE_LENGTH: float = 10_000.0  # Standard surface length in metres
TOFPA_REF_LINE_HALF_WIDTH: float = 3_000.0  # Reference line half-width in metres


class TOFPA:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = self.tr(u'&TOFPA')
        self.first_start = True
        self.panel = None

    def tr(self, message):
        """Get the translation for a string using Qt translation API."""
        return QCoreApplication.translate('TOFPA', message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self) -> None:
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'TOFPA'),
            callback=self.show_panel,
            parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self) -> None:
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&TOFPA'), action)
            self.iface.removeToolBarIcon(action)
        # Remove the panel if it's open
        if self.panel:
            self.iface.removeDockWidget(self.panel)
            self.panel = None

    def show_panel(self) -> None:
        """Toggle the TOFPA dockwidget panel (show/hide)."""
        if not self.panel:
            # Create panel if it doesn't exist
            self.panel = TofpaDockWidget(self.iface)
            self.iface.addDockWidget(DOCK_RIGHT, self.panel)
            self.panel.calculateClicked.connect(self.on_calculate)
            self.panel.closeClicked.connect(self.on_close_panel)
            self.panel.show()
            self.panel.raise_()
        else:
            # Panel exists, toggle its visibility
            if self.panel.isVisible():
                self.panel.hide()
            else:
                self.panel.show()
                self.panel.raise_()

    def on_close_panel(self) -> None:
        """Hide the panel when close is clicked."""
        if self.panel:
            self.panel.hide()

    def on_calculate(self) -> None:
        """Build parameter dataclasses from the UI and trigger surface calculation."""
        raw = self.panel.get_parameters()
        tofpa_params = TofpaParams.from_dict(raw)
        obs_params = ObstacleParams.from_dict(raw)
        success = self.create_tofpa_surface(tofpa_params, obs_params)
        if success:
            self.iface.messageBar().pushMessage(
                "TOFPA:", "TakeOff Climb Surface Calculation Finished", level=Qgis.Success
            )

    def get_single_feature(self, layer, use_selected_feature, feature_type="feature"):
        """
        Get a single feature from the layer following the original selection logic.
        Returns the feature if successful, None if error (with error message displayed).
        """
        if use_selected_feature:
            selected_features = layer.selectedFeatures()
            if len(selected_features) == 1:
                return selected_features[0]
            elif len(selected_features) > 1:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"Please select only one {feature_type} in layer '{layer.name()}'.", 
                    level=Qgis.Critical
                )
                return None
            else:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"No {feature_type} selected in layer '{layer.name()}'. Please select one.", 
                    level=Qgis.Critical
                )
                return None
        else:
            all_features = list(layer.getFeatures())
            if len(all_features) == 1:
                return all_features[0]
            elif len(all_features) > 1:
                self.iface.messageBar().pushMessage(
                    "Error", 
                    f"Layer '{layer.name()}' has more than one {feature_type}. Please select one and check 'Use selected features only'.", 
                    level=Qgis.Critical
                )
                return None
            elif len(all_features) == 0:
                self.iface.messageBar().pushMessage(
                    "Error",
                    f"No {feature_type}s found in layer '{layer.name()}'.",
                    level=Qgis.Critical
                )
                return None
            # Fallback: no condition matched
            return None

    def _validate_params(self, params: TofpaParams) -> list[str]:
        """
        Validate TOFPA surface parameters before calculation.

        Returns a (possibly empty) list of human-readable error strings.
        An empty list means the parameters are valid.
        """
        errors: list[str] = []
        if params.width_tofpa <= 0:
            errors.append("Initial width must be greater than 0 m")
        if params.max_width_tofpa < params.width_tofpa:
            errors.append("Maximum width must be ≥ initial width")
        if params.max_width_tofpa == params.width_tofpa:
            errors.append("Max width equals initial width — surface will have no divergence")
        if params.runway_layer_id is None:
            errors.append("No runway layer selected")
        if params.threshold_layer_id is None:
            errors.append("No threshold layer selected")
        return errors

    def create_tofpa_surface(self, params: TofpaParams, obs_params: ObstacleParams) -> bool:
        """Create the TOFPA AOC Type A surface and add it to the QGIS map. Returns True on success."""
        # Validate before touching QGIS
        errors = self._validate_params(params)
        if errors:
            self.iface.messageBar().pushMessage(
                "TOFPA Validation", "; ".join(errors), level=Qgis.Critical
            )
            return False

        # Unpack into local names — keeps the rest of the geometry code unchanged
        width_tofpa = params.width_tofpa
        max_width_tofpa = params.max_width_tofpa
        cwy_length = params.cwy_length
        z0 = params.z0
        ze = params.ze
        s = params.s
        runway_layer_id = params.runway_layer_id
        threshold_layer_id = params.threshold_layer_id
        use_selected_feature = params.use_selected_feature
        export_kmz = params.export_kmz
        export_aixm = params.export_aixm
        include_obstacles = obs_params.include_obstacles
        obstacles_layer_id = obs_params.obstacles_layer_id
        obstacle_height_field = obs_params.obstacle_height_field
        obstacle_buffer = obs_params.obstacle_buffer
        min_obstacle_height = obs_params.min_obstacle_height
        enable_shadow_analysis = obs_params.enable_shadow_analysis
        shadow_tolerance = obs_params.shadow_tolerance

        map_srid = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Get runway layer by ID
        runway_layer = QgsProject.instance().mapLayer(runway_layer_id)
        if not runway_layer:
            self.iface.messageBar().pushMessage("Error", "Selected runway layer not found!", level=Qgis.Critical)
            return False
        
        # Get single runway feature using robust selection logic
        runway_feature = self.get_single_feature(runway_layer, use_selected_feature, "runway feature")
        if not runway_feature:
            return False
        
        # Get runway geometry (from original script)
        rwy_geom = runway_feature.geometry()
        rwy_length = rwy_geom.length()
        # TODO (BUG-05): rwy_slope is calculated but never applied to surface point elevations.
        # Verify with ICAO Doc 8168 whether runway slope should offset Z values of pt_01D/pt_02D/pt_03D.
        rwy_slope = (z0 - ze) / rwy_length if rwy_length > 0 else 0  # noqa: F841
        logger.debug("Runway length: %s", rwy_length)
        
        # Get the azimuth of the line (from original script)
        geom = runway_feature.geometry().asPolyline()
        if len(geom) < 2:
            self.iface.messageBar().pushMessage("Error", "Runway geometry must have at least 2 points!", level=Qgis.Critical)
            return False
            
        # Calculate azimuth based on runway direction (simplified logic)
        # s=0 means takeoff from start to end, s=-1 means takeoff from end to start
        if s == 0:
            # Takeoff from start to end: use first to last point
            start_point = QgsPoint(geom[0])   # first point (runway start)
            end_point = QgsPoint(geom[-1])    # last point (runway end)
        else:  # s == -1
            # Takeoff from end to start: use last to first point  
            start_point = QgsPoint(geom[-1])  # last point (runway end)
            end_point = QgsPoint(geom[0])     # first point (runway start)
        
        # Calculate takeoff direction azimuth directly
        azimuth = start_point.azimuth(end_point)  # azimuth in takeoff direction
        bazimuth = azimuth + 180  # opposite direction (backward from azimuth)
        
        logger.debug("Start point: %s, %s", start_point.x(), start_point.y())
        logger.debug("End point: %s, %s", end_point.x(), end_point.y())
        logger.debug("Takeoff azimuth: %s", azimuth)
        logger.debug("Backward azimuth: %s", bazimuth)
        logger.debug("s parameter: %s", s)
        
        # Get the threshold point from selected layer
        threshold_layer = QgsProject.instance().mapLayer(threshold_layer_id)
        if not threshold_layer:
            self.iface.messageBar().pushMessage("Error", "Selected threshold layer not found!", level=Qgis.Critical)
            return False
        
        # Get single threshold feature using robust selection logic
        threshold_feature = self.get_single_feature(threshold_layer, use_selected_feature, "threshold feature")
        if not threshold_feature:
            return False
        
        # Get threshold point (from original script)
        new_geom = QgsPoint(threshold_feature.geometry().asPoint())
        new_geom.addZValue(z0)
        
        logger.debug("Threshold point: %s, %s, %s", new_geom.x(), new_geom.y(), new_geom.z())
        logger.debug("Parameters - Width: %s, Max Width: %s", width_tofpa, max_width_tofpa)
        logger.debug("CWY Length: %s, Z0: %s, ZE: %s", cwy_length, z0, ze)
        
        list_pts = []
        # Origin (from original script)
        pt_0D = new_geom
        
        # Distance for surface start (from original script)
        if cwy_length == 0:
            dD = 0  # there is a condition to use the runway strip to analyze
        else:
            dD = cwy_length
        logger.debug("dD (distance for surface start): %s", dD)
        
        # Calculate all points for the TOFPA surface using PROJECT method (ORIGINAL LOGIC)
        # First project backward from threshold to get the start point (if CWY length > 0)
        pt_01D = new_geom.project(dD, azimuth)  # Project from threshold by CWY length in the direction of the flight
        pt_01D.setZ(ze)
        logger.debug("pt_01D (start point): %s, %s, %s", pt_01D.x(), pt_01D.y(), pt_01D.z())
        pt_01DL = pt_01D.project(width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular direction
        pt_01DR = pt_01D.project(width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular direction
        
        # Distance to reach maximum width (from original script - ALL use azimuth for forward projection)
        pt_02D = pt_01D.project(((max_width_tofpa/2-width_tofpa/2)/TOFPA_DIVERGENCE_RATIO), azimuth)
        pt_02D.setZ(ze+((max_width_tofpa/2-width_tofpa/2)/TOFPA_DIVERGENCE_RATIO)*TOFPA_CLIMB_GRADIENT)
        pt_02DL = pt_02D.project(max_width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular
        pt_02DR = pt_02D.project(max_width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular
        
        # Distance to end of TakeOff Climb Surface (from original script - ALL use azimuth for forward projection)
        pt_03D = pt_01D.project(TOFPA_SURFACE_LENGTH, azimuth)
        pt_03D.setZ(ze+TOFPA_SURFACE_LENGTH*TOFPA_CLIMB_GRADIENT)
        pt_03DL = pt_03D.project(max_width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular
        pt_03DR = pt_03D.project(max_width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular
        
        list_pts.extend((pt_0D, pt_01D, pt_01DL, pt_01DR, pt_02D, pt_02DL, pt_02DR, pt_03D, pt_03DL, pt_03DR))
        
        # Create reference line perpendicular to trajectory at start point (3000m each side)
        # The start point depends on whether CWY exists or not
        reference_start_point = pt_01D  # This is the calculated start point (considers CWY)
        
        # Create points 3000m on each side perpendicular to the azimuth
        ref_line_left = reference_start_point.project(TOFPA_REF_LINE_HALF_WIDTH, azimuth+90)  # 3000m to the left
        ref_line_right = reference_start_point.project(TOFPA_REF_LINE_HALF_WIDTH, azimuth-90)  # 3000m to the right
        
        # Set same elevation as start point
        ref_line_left.setZ(reference_start_point.z())
        ref_line_right.setZ(reference_start_point.z())
        
        logger.debug("Reference line left point: %s, %s, %s", ref_line_left.x(), ref_line_left.y(), ref_line_left.z())
        logger.debug("Reference line right point: %s, %s, %s", ref_line_right.x(), ref_line_right.y(), ref_line_right.z())
        
        # Create reference line memory layer
        ref_layer = QgsVectorLayer(f"LineStringZ?crs={map_srid}", "reference_line", "memory")
        ref_id_field = QgsField('id', FIELD_INT)
        ref_label_field = QgsField('txt-label', FIELD_STRING)
        ref_layer.dataProvider().addAttributes([ref_id_field, ref_label_field])
        ref_layer.updateFields()
        
        # Create the reference line feature
        ref_feature = QgsFeature()
        ref_line_geom = QgsLineString([ref_line_left, ref_line_right])
        ref_feature.setGeometry(QgsGeometry(ref_line_geom))
        ref_feature.setAttributes([1, 'tofpa reference line'])
        ref_layer.dataProvider().addFeatures([ref_feature])
        
        # Style the reference line (red color, width 0.25)
        ref_symbol = QgsLineSymbol.createSimple({
            'color': '255,0,0,255',  # Red color
            'width': '0.25'
        })
        ref_layer.renderer().setSymbol(ref_symbol)
        ref_layer.triggerRepaint()
        
        # Add reference line layer to map
        QgsProject.instance().addMapLayers([ref_layer])
        
        # Creation of the Take Off Climb Surfaces (from original script)
        # Create memory layer
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "RWY_TOFPA_AOC_TypeA", "memory")
        id_field = QgsField('ID', FIELD_STRING)
        name_field = QgsField('SurfaceName', FIELD_STRING)
        v_layer.dataProvider().addAttributes([id_field])
        v_layer.dataProvider().addAttributes([name_field])
        v_layer.updateFields()
        
        # Take Off Climb Surface Creation (from original script)
        surface_area = [pt_03DR, pt_03DL, pt_02DL, pt_01DL, pt_01DR, pt_02DR]
        pr = v_layer.dataProvider()
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(surface_area), rings=[]))
        seg.setAttributes([13, 'TOFPA AOC Type A'])
        pr.addFeatures([seg])
        
        # Load PolygonZ Layer to map canvas (from original script)
        QgsProject.instance().addMapLayers([v_layer])
        
        # Change style of layer (from original script but using modern syntax)
        symbol = QgsFillSymbol.createSimple({
            'color': '128,128,128,102',  # Grey with 40% opacity
            'outline_color': '0,0,0,255',
            'outline_width': '0.5'
        })
        v_layer.renderer().setSymbol(symbol)
        v_layer.triggerRepaint()
        
        # Process survey obstacles if requested
        obstacles_layers = []
        if include_obstacles and obstacles_layer_id:
            try:
                obstacles_info = self.process_survey_obstacles(
                    obs_params,
                    v_layer,      # TOFPA surface for intersection analysis
                    use_selected_feature,
                )
                if obstacles_info:
                    obstacles_layers = obstacles_info['layers']
                    
                    # Create result message including shadow analysis if performed
                    message = f"Analyzed {obstacles_info['total_obstacles']} obstacles, {obstacles_info['critical_obstacles']} are critical"
                    
                    if enable_shadow_analysis and 'shadow_results' in obstacles_info:
                        shadow_results = obstacles_info['shadow_results']
                        shadowed_count = len(shadow_results.get('shadowed_obstacles', []))
                        visible_count = len([obs for obs in shadow_results.get('visible_obstacles', []) if obs.get('is_critical', False)])
                        message += f", {shadowed_count} shadowed, {visible_count} visible"
                    
                    # Display obstacles analysis results
                    self.iface.messageBar().pushMessage(
                        "Obstacles Analysis:", 
                        message, 
                        level=Qgis.Info
                    )
            except Exception as e:
                logger.warning("Obstacles analysis failed: %s", e)
                self.iface.messageBar().pushMessage(
                    "Warning", 
                    f"Obstacles analysis failed: {str(e)}", 
                    level=Qgis.Warning
                )
        
        # Prepare layers for export (include obstacles if they exist)
        layers_to_export = [v_layer, ref_layer] + obstacles_layers
        
        # Export to KMZ if requested
        if export_kmz:
            self.export_to_kmz(layers_to_export)
        
        # Export to AIXM if requested
        if export_aixm:
            self.export_to_aixm(layers_to_export)
        
        # Zoom to layer (from original script)
        v_layer.selectAll()
        canvas = self.iface.mapCanvas()
        canvas.zoomToSelected(v_layer)
        v_layer.removeSelection()
        
        # Get canvas scale (from original script)
        sc = canvas.scale()
        if sc < 20000:
            sc = 20000
        canvas.zoomScale(sc)
        
        return True

    def process_survey_obstacles(
        self,
        obs_params: ObstacleParams,
        tofpa_surface_layer,
        use_selected_feature: bool,
    ) -> dict:
        """
        Process survey obstacles and analyse their impact on the TOFPA surface.

        Delegates all geometry / shadow work to ``ObstacleAnalyzer``; this method
        only handles QGIS layer look-up and feature retrieval.
        """
        obstacles_layer = QgsProject.instance().mapLayer(obs_params.obstacles_layer_id)
        if not obstacles_layer:
            raise ValueError("Selected obstacles layer not found!")

        field_names = [f.name() for f in obstacles_layer.fields()]
        if obs_params.obstacle_height_field and obs_params.obstacle_height_field not in field_names:
            raise ValueError(
                f"Height field '{obs_params.obstacle_height_field}' not found in obstacles layer!"
            )

        if use_selected_feature:
            features = obstacles_layer.selectedFeatures()
            if not features:
                raise ValueError(
                    "No obstacles selected. Please select obstacles or uncheck "
                    "'Use selected features only'."
                )
        else:
            features = list(obstacles_layer.getFeatures())

        if not features:
            raise ValueError("No obstacles found in layer.")

        analyzer = ObstacleAnalyzer()
        layers_info = analyzer.create_layers(obstacles_layer.crs())

        critical_obstacles = 0
        total_obstacles = 0
        obstacles_data: list[dict] = []

        for feature in features:
            try:
                obstacle_info = analyzer.analyze_single(
                    feature,
                    obs_params.obstacle_height_field,
                    obs_params.obstacle_buffer,
                    obs_params.min_obstacle_height,
                    tofpa_surface_layer,
                    layers_info,
                )
                total_obstacles += 1
                if obstacle_info["is_critical"]:
                    critical_obstacles += 1
                obstacles_data.append({
                    "feature": feature,
                    "obstacle_info": obstacle_info,
                    "point": obstacle_info["obstacle_point"],
                    "height": obstacle_info["height"],
                    "is_critical": obstacle_info["is_critical"],
                })
            except Exception as exc:
                logger.warning("Failed to process obstacle feature %s: %s", feature.id(), exc)

        shadow_results: dict = {"shadowed_obstacles": [], "visible_obstacles": obstacles_data}
        if obs_params.enable_shadow_analysis:
            shadow_results = analyzer.perform_shadow_analysis(
                obstacles_data, tofpa_surface_layer, obs_params.shadow_tolerance
            )
            # BUG-02 fix: use actual buffer, not hardcoded 10.0
            analyzer.apply_shadow_results(layers_info, shadow_results, obs_params.obstacle_buffer)

        analyzer.finalize_layers(layers_info)

        return {
            "layers": [
                layers_info["critical_layer"],
                layers_info["safe_layer"],
                layers_info["buffer_layer"],
                layers_info.get("shadowed_layer"),
                layers_info.get("visible_layer"),
            ],
            "total_obstacles": total_obstacles,
            "critical_obstacles": critical_obstacles,
            "shadow_results": shadow_results,
        }


    def export_to_kmz(self, layers: list) -> bool:
        """Export layers to KMZ format for Google Earth with proper styling."""
        # Handle both single layer and list of layers
        if not isinstance(layers, list):
            layers = [layers]
        
        # Check if any layer has features
        has_features = any(layer.featureCount() > 0 for layer in layers)
        if not has_features:
            self.iface.messageBar().pushMessage(
                "Error", 
                "No features to export in any layer", 
                level=Qgis.Critical
            )
            return False
            
        # Ask user for save location
        file_dialog = QFileDialog()
        file_dialog.setDefaultSuffix('kmz')
        file_path, _ = file_dialog.getSaveFileName(
            None, 
            "Save KMZ File", 
            "", 
            "KMZ Files (*.kmz)"
        )
        
        if not file_path:
            self.iface.messageBar().pushMessage(
                "Info", 
                "KMZ export cancelled by user", 
                level=Qgis.Info
            )
            return False
        
        # Ensure file has .kmz extension
        if not file_path.lower().endswith('.kmz'):
            file_path += '.kmz'
        
        # Convert KML to KMZ (zip multiple KML files)
        import zipfile
        try:
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                temp_files = []
                
                for i, layer in enumerate(layers):
                    if layer.featureCount() == 0:
                        continue
                        
                    # Set up KML options with proper styling and absolute altitude
                    options = QgsVectorFileWriter.SaveVectorOptions()
                    options.driverName = "KML"
                    options.layerName = layer.name()
                    
                    # Set KML to use absolute altitude (not clamped to ground)
                    options.datasourceOptions = ['ALTITUDE_MODE=absolute']
                    
                    # KML uses EPSG:4326 (WGS84)
                    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
                    options.ct = QgsCoordinateTransform(
                        layer.crs(), 
                        crs_4326, 
                        QgsProject.instance()
                    )
                    
                    # Write to temporary KML
                    temp_kml = file_path.replace('.kmz', f'_{i}_{layer.name()}.kml')
                    temp_files.append(temp_kml)
                    
                    result = QgsVectorFileWriter.writeAsVectorFormatV2(
                        layer,
                        temp_kml,
                        QgsProject.instance().transformContext(),
                        options
                    )
                    
                    if result[0] != QgsVectorFileWriter.NoError:
                        self.iface.messageBar().pushMessage(
                            "Error", 
                            f"Failed to export layer {layer.name()} to KML: {result[1]}", 
                            level=Qgis.Critical
                        )
                        continue
                    
                    # Add KML file to ZIP
                    zipf.write(temp_kml, os.path.basename(temp_kml))
                
                # Remove temporary KML files
                for temp_file in temp_files:
                    try:
                        os.remove(temp_file)
                    except PermissionError:
                        self.iface.messageBar().pushMessage(
                            "Warning", 
                            f"Could not delete temporary KML file: {temp_file}", 
                            level=Qgis.Warning
                        )
            
            self.iface.messageBar().pushMessage(
                "Success", 
                f"Exported {len(layers)} layers to KMZ: {file_path}", 
                level=Qgis.Success
            )
            return True
            
        except Exception as e:
            logger.error("Failed to create KMZ file: %s", e)
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to create KMZ file: {str(e)}", 
                level=Qgis.Critical
            )
            return False

    def export_to_aixm(self, layers: list) -> bool:
        """Export layers to AIXM 5.1.1 format for aviation data exchange."""
        # Handle both single layer and list of layers
        if not isinstance(layers, list):
            layers = [layers]
        
        # Check if any layer has features
        has_features = any(layer.featureCount() > 0 for layer in layers)
        if not has_features:
            self.iface.messageBar().pushMessage(
                "Error", 
                "No features to export in any layer", 
                level=Qgis.Critical
            )
            return False
            
        # Ask user for save location
        file_dialog = QFileDialog()
        file_dialog.setDefaultSuffix('xml')
        file_path, _ = file_dialog.getSaveFileName(
            None, 
            "Save AIXM File", 
            "", 
            "AIXM Files (*.xml)"
        )
        
        if not file_path:
            self.iface.messageBar().pushMessage(
                "Info", 
                "AIXM export cancelled by user", 
                level=Qgis.Info
            )
            return False
        
        # Ensure file has .xml extension
        if not file_path.lower().endswith('.xml'):
            file_path += '.xml'
        
        try:
            generate_aixm_file(layers, file_path)

            self.iface.messageBar().pushMessage(
                "Success",
                f"Exported {len(layers)} layers to AIXM: {file_path}", 
                level=Qgis.Success
            )
            return True
            
        except Exception as e:
            logger.error("Failed to create AIXM file: %s", e)
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to create AIXM file: {str(e)}", 
                level=Qgis.Critical
            )
            return False

