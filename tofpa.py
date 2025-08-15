# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPA
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool
                              -------------------
        begin                : 2024-04-14
        copyright            : (C) 2024
        email                : your.email@example.com
 ***************************************************************************/

 /***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QCoreApplication, QVariant, Qt
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QAction
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
                      QgsPoint, QgsField, QgsPolygon, QgsLineString, Qgis, 
                      QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem, QgsWkbTypes)

import os.path
from math import *

# Import the dockwidget with error handling
try:
    from .tofpa_dockwidget import TofpaDockWidget
except ImportError as e:
    print(f"Import error: {e}")
    # Fallback import
    import sys
    import os
    plugin_dir = os.path.dirname(__file__)
    sys.path.insert(0, plugin_dir)
    from tofpa_dockwidget import TofpaDockWidget

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

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'TOFPA'),
            callback=self.show_panel,
            parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&TOFPA'), action)
            self.iface.removeToolBarIcon(action)
        # Remove the panel if it's open
        if self.panel:
            self.iface.removeDockWidget(self.panel)
            self.panel = None

    def show_panel(self):
        """Toggle the TOFPA dockwidget panel (show/hide)"""
        if not self.panel:
            # Create panel if it doesn't exist
            self.panel = TofpaDockWidget(self.iface)
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.panel)
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

    def on_close_panel(self):
        """Hide the panel when close is clicked"""
        if self.panel:
            self.panel.hide()

    def on_calculate(self):
        """Calculate TOFPA surface using parameters from the UI"""
        params = self.panel.get_parameters()
        success = self.create_tofpa_surface(
            params['width_tofpa'],
            params['max_width_tofpa'],
            params['cwy_length'],
            params['z0'],
            params['ze'],
            params['s'],
            params['runway_layer_id'],
            params['threshold_layer_id'],
            params['use_selected_feature'],
            params['export_kmz'],
            params['export_aixm'],
            params['include_obstacles'],
            params['obstacles_layer_id'],
            params['obstacle_height_field'],
            params['obstacle_buffer'],
            params['min_obstacle_height']
        )
        if success:
            self.iface.messageBar().pushMessage("TOFPA:", "TakeOff Climb Surface Calculation Finished", level=Qgis.Success)

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

    def create_tofpa_surface(self, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, 
                            runway_layer_id, threshold_layer_id, use_selected_feature, export_kmz, export_aixm,
                            include_obstacles, obstacles_layer_id, obstacle_height_field, obstacle_buffer, min_obstacle_height):
        """Create the TOFPA surface with the given parameters - ORIGINAL LOGIC + OBSTACLES"""
        
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
        rwy_slope = (z0-ze)/rwy_length if rwy_length > 0 else 0
        print(f"Runway length: {rwy_length}")
        
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
        
        print(f"Start point: {start_point.x()}, {start_point.y()}")
        print(f"End point: {end_point.x()}, {end_point.y()}")
        print(f"Takeoff azimuth: {azimuth}")
        print(f"Backward azimuth: {bazimuth}")
        print(f"s parameter: {s}")
        
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
        
        print(f"Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
        print(f"Parameters - Width: {width_tofpa}, Max Width: {max_width_tofpa}")
        print(f"CWY Length: {cwy_length}, Z0: {z0}, ZE: {ze}")
        
        list_pts = []
        # Origin (from original script)
        pt_0D = new_geom
        
        # Distance for surface start (from original script)
        if cwy_length == 0:
            dD = 0  # there is a condition to use the runway strip to analyze
        else:
            dD = cwy_length
        print(f"dD (distance for surface start): {dD}")
        
        # Calculate all points for the TOFPA surface using PROJECT method (ORIGINAL LOGIC)
        # First project backward from threshold to get the start point (if CWY length > 0)
        pt_01D = new_geom.project(dD, bazimuth)  # Project backward from threshold by CWY length
        pt_01D.setZ(ze)
        print(f"pt_01D (start point): {pt_01D.x()}, {pt_01D.y()}, {pt_01D.z()}")
        pt_01DL = pt_01D.project(width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular direction
        pt_01DR = pt_01D.project(width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular direction
        
        # Distance to reach maximum width (from original script - ALL use azimuth for forward projection)
        pt_02D = pt_01D.project(((max_width_tofpa/2-width_tofpa/2)/0.125), azimuth)
        pt_02D.setZ(ze+((max_width_tofpa/2-width_tofpa/2)/0.125)*0.012)
        pt_02DL = pt_02D.project(max_width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular
        pt_02DR = pt_02D.project(max_width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular
        
        # Distance to end of TakeOff Climb Surface (from original script - ALL use azimuth for forward projection)
        pt_03D = pt_01D.project(10000, azimuth)
        pt_03D.setZ(ze+10000*0.012)
        pt_03DL = pt_03D.project(max_width_tofpa/2, azimuth+90)  # Use azimuth for perpendicular
        pt_03DR = pt_03D.project(max_width_tofpa/2, azimuth-90)  # Use azimuth for perpendicular
        
        list_pts.extend((pt_0D, pt_01D, pt_01DL, pt_01DR, pt_02D, pt_02DL, pt_02DR, pt_03D, pt_03DL, pt_03DR))
        
        # Create reference line perpendicular to trajectory at start point (3000m each side)
        # The start point depends on whether CWY exists or not
        reference_start_point = pt_01D  # This is the calculated start point (considers CWY)
        
        # Create points 3000m on each side perpendicular to the azimuth
        ref_line_left = reference_start_point.project(3000, azimuth+90)  # 3000m to the left
        ref_line_right = reference_start_point.project(3000, azimuth-90)  # 3000m to the right
        
        # Set same elevation as start point
        ref_line_left.setZ(reference_start_point.z())
        ref_line_right.setZ(reference_start_point.z())
        
        print(f"Reference line left point: {ref_line_left.x()}, {ref_line_left.y()}, {ref_line_left.z()}")
        print(f"Reference line right point: {ref_line_right.x()}, {ref_line_right.y()}, {ref_line_right.z()}")
        
        # Create reference line memory layer
        ref_layer = QgsVectorLayer(f"LineStringZ?crs={map_srid}", "reference_line", "memory")
        ref_id_field = QgsField('id', QVariant.Int)
        ref_label_field = QgsField('txt-label', QVariant.String)
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
        id_field = QgsField('ID', QVariant.String)
        name_field = QgsField('SurfaceName', QVariant.String)
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
                    obstacles_layer_id, 
                    obstacle_height_field, 
                    obstacle_buffer, 
                    min_obstacle_height,
                    v_layer,  # TOFPA surface for intersection analysis
                    use_selected_feature
                )
                if obstacles_info:
                    obstacles_layers = obstacles_info['layers']
                    # Display obstacles analysis results
                    self.iface.messageBar().pushMessage(
                        "Obstacles Analysis:", 
                        f"Analyzed {obstacles_info['total_obstacles']} obstacles, "
                        f"{obstacles_info['critical_obstacles']} are critical", 
                        level=Qgis.Info
                    )
            except Exception as e:
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

    def process_survey_obstacles(self, obstacles_layer_id, height_field, buffer_distance, 
                                min_height, tofpa_surface_layer, use_selected_feature):
        """
        Process survey obstacles and analyze their impact on TOFPA surface.
        
        This creates a separate model that works with survey obstacles while
        a process is derived to run both analyses simultaneously to produce a final output.
        """
        # Get obstacles layer
        obstacles_layer = QgsProject.instance().mapLayer(obstacles_layer_id)
        if not obstacles_layer:
            raise Exception("Selected obstacles layer not found!")
        
        # Validate height field
        field_names = [field.name() for field in obstacles_layer.fields()]
        if height_field and height_field not in field_names:
            raise Exception(f"Height field '{height_field}' not found in obstacles layer!")
        
        # Get features to process
        if use_selected_feature:
            features = obstacles_layer.selectedFeatures()
            if not features:
                raise Exception("No obstacles selected in layer. Please select obstacles or uncheck 'Use selected features only'.")
        else:
            features = list(obstacles_layer.getFeatures())
        
        if not features:
            raise Exception("No obstacles found in layer.")
        
        # Create layers for obstacles analysis
        layers_info = self._create_obstacles_layers(obstacles_layer.crs())
        
        # Process each obstacle
        critical_obstacles = 0
        total_obstacles = 0
        
        for feature in features:
            try:
                obstacle_info = self._analyze_single_obstacle(
                    feature, height_field, buffer_distance, min_height, 
                    tofpa_surface_layer, layers_info
                )
                total_obstacles += 1
                if obstacle_info['is_critical']:
                    critical_obstacles += 1
            except Exception as e:
                print(f"Warning: Failed to process obstacle feature {feature.id()}: {str(e)}")
                continue
        
        # Add layers to map and style them
        self._finalize_obstacles_layers(layers_info)
        
        return {
            'layers': [layers_info['critical_layer'], layers_info['safe_layer'], layers_info['buffer_layer']],
            'total_obstacles': total_obstacles,
            'critical_obstacles': critical_obstacles
        }

    def _create_obstacles_layers(self, crs):
        """Create memory layers for obstacles analysis"""
        # Critical obstacles layer (red)
        critical_layer = QgsVectorLayer(f"PointZ?crs={crs.authid()}", "Critical_Obstacles", "memory")
        critical_fields = [
            QgsField('id', QVariant.Int),
            QgsField('height', QVariant.Double),
            QgsField('buffer_m', QVariant.Double),
            QgsField('status', QVariant.String),
            QgsField('intersection', QVariant.String)
        ]
        critical_layer.dataProvider().addAttributes(critical_fields)
        critical_layer.updateFields()
        
        # Safe obstacles layer (green)
        safe_layer = QgsVectorLayer(f"PointZ?crs={crs.authid()}", "Safe_Obstacles", "memory")
        safe_layer.dataProvider().addAttributes(critical_fields)
        safe_layer.updateFields()
        
        # Buffer zones layer (yellow)
        buffer_layer = QgsVectorLayer(f"PolygonZ?crs={crs.authid()}", "Obstacle_Buffers", "memory")
        buffer_fields = [
            QgsField('obstacle_id', QVariant.Int),
            QgsField('buffer_m', QVariant.Double),
            QgsField('status', QVariant.String)
        ]
        buffer_layer.dataProvider().addAttributes(buffer_fields)
        buffer_layer.updateFields()
        
        return {
            'critical_layer': critical_layer,
            'safe_layer': safe_layer,
            'buffer_layer': buffer_layer
        }

    def _analyze_single_obstacle(self, feature, height_field, buffer_distance, min_height, 
                                tofpa_surface_layer, layers_info):
        """Analyze a single obstacle against TOFPA surface"""
        # Get obstacle geometry and height
        geom = feature.geometry()
        if not geom or geom.isEmpty():
            raise Exception("Invalid geometry")
        
        # Get height from field or use minimum height
        obstacle_height = min_height
        if height_field:
            height_value = feature.attribute(height_field)
            if height_value is not None and isinstance(height_value, (int, float)):
                obstacle_height = max(float(height_value), min_height)
        
        # Create point geometry with height
        if geom.type() == QgsWkbTypes.PolygonGeometry:
            # Use centroid for polygons
            centroid = geom.centroid().asPoint()
            obstacle_point = QgsPoint(centroid.x(), centroid.y(), obstacle_height)
        else:
            # Use point directly
            point = geom.asPoint()
            obstacle_point = QgsPoint(point.x(), point.y(), obstacle_height)
        
        # Create buffer around obstacle
        buffer_geom = QgsGeometry.fromPointXY(QgsPoint(obstacle_point.x(), obstacle_point.y())).buffer(buffer_distance, 16)
        
        # Check intersection with TOFPA surface
        is_critical = False
        intersection_type = "None"
        
        for tofpa_feature in tofpa_surface_layer.getFeatures():
            tofpa_geom = tofpa_feature.geometry()
            if buffer_geom.intersects(tofpa_geom):
                is_critical = True
                intersection_type = "Buffer intersects TOFPA surface"
                break
        
        # Add to appropriate layer
        obstacle_feature = QgsFeature()
        obstacle_feature.setGeometry(QgsGeometry(obstacle_point))
        obstacle_feature.setAttributes([
            int(feature.id()),
            obstacle_height,
            buffer_distance,
            "CRITICAL" if is_critical else "SAFE",
            intersection_type
        ])
        
        # Add buffer feature
        buffer_feature = QgsFeature()
        buffer_feature.setGeometry(buffer_geom)
        buffer_feature.setAttributes([
            int(feature.id()),
            buffer_distance,
            "CRITICAL" if is_critical else "SAFE"
        ])
        
        # Add to appropriate layers
        if is_critical:
            layers_info['critical_layer'].dataProvider().addFeatures([obstacle_feature])
        else:
            layers_info['safe_layer'].dataProvider().addFeatures([obstacle_feature])
        
        layers_info['buffer_layer'].dataProvider().addFeatures([buffer_feature])
        
        return {
            'is_critical': is_critical,
            'height': obstacle_height,
            'intersection_type': intersection_type
        }

    def _finalize_obstacles_layers(self, layers_info):
        """Add obstacles layers to map and apply styling"""
        # Style critical obstacles (red)
        critical_symbol = QgsMarkerSymbol.createSimple({
            'color': '255,0,0,255',  # Red
            'size': '4',
            'outline_color': '0,0,0,255'
        })
        layers_info['critical_layer'].renderer().setSymbol(critical_symbol)
        
        # Style safe obstacles (green)
        safe_symbol = QgsMarkerSymbol.createSimple({
            'color': '0,255,0,255',  # Green
            'size': '3',
            'outline_color': '0,0,0,255'
        })
        layers_info['safe_layer'].renderer().setSymbol(safe_symbol)
        
        # Style buffer zones (yellow with transparency)
        buffer_symbol = QgsFillSymbol.createSimple({
            'color': '255,255,0,100',  # Yellow with transparency
            'outline_color': '255,165,0,255',  # Orange outline
            'outline_width': '0.3'
        })
        layers_info['buffer_layer'].renderer().setSymbol(buffer_symbol)
        
        # Add all layers to map
        QgsProject.instance().addMapLayers([
            layers_info['critical_layer'],
            layers_info['safe_layer'], 
            layers_info['buffer_layer']
        ])

    def export_to_kmz(self, layers):
        """Export layers to KMZ format for Google Earth with proper styling"""
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
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to create KMZ file: {str(e)}", 
                level=Qgis.Critical
            )
            return False

    def export_to_aixm(self, layers):
        """Export layers to AIXM 5.1.1 format for aviation data exchange"""
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
            self._generate_aixm_file(layers, file_path)
            
            self.iface.messageBar().pushMessage(
                "Success", 
                f"Exported {len(layers)} layers to AIXM: {file_path}", 
                level=Qgis.Success
            )
            return True
            
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to create AIXM file: {str(e)}", 
                level=Qgis.Critical
            )
            return False

    def _generate_aixm_file(self, layers, file_path):
        """Generate AIXM 5.1.1 compliant XML file"""
        import xml.etree.ElementTree as ET
        from datetime import datetime
        import uuid
        
        # Create root element with AIXM 5.1.1 namespace
        root = ET.Element("aixm:AIXMBasicMessage")
        root.set("xmlns:aixm", "http://www.aixm.aero/schema/5.1.1")
        root.set("xmlns:gml", "http://www.opengis.net/gml/3.2")
        root.set("xmlns:xlink", "http://www.w3.org/1999/xlink")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:schemaLocation", "http://www.aixm.aero/schema/5.1.1 http://www.aixm.aero/schema/5.1.1/AIXM_BasicMessage.xsd")
        
        # Add message metadata
        header = ET.SubElement(root, "gml:boundedBy")
        ET.SubElement(header, "gml:Null").text = "unknown"
        
        # Add feature member for each layer
        for layer in layers:
            if layer.featureCount() == 0:
                continue
                
            if "reference_line" in layer.name().lower():
                self._add_aixm_reference_line(root, layer)
            else:
                self._add_aixm_surface(root, layer)
        
        # Write to file with proper formatting
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ", level=0)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)

    def _add_aixm_surface(self, root, layer):
        """Add TOFPA surface as AIXM NavigationArea"""
        import xml.etree.ElementTree as ET
        import uuid
        from datetime import datetime
        
        for feature in layer.getFeatures():
            # Create feature member
            feature_member = ET.SubElement(root, "gml:featureMember")
            nav_area = ET.SubElement(feature_member, "aixm:NavigationArea")
            nav_area.set("gml:id", f"tofpa_surface_{uuid.uuid4().hex[:8]}")
            
            # Add time slice
            time_slice = ET.SubElement(nav_area, "aixm:timeSlice")
            nav_area_ts = ET.SubElement(time_slice, "aixm:NavigationAreaTimeSlice")
            nav_area_ts.set("gml:id", f"ts_{uuid.uuid4().hex[:8]}")
            
            # Valid time
            valid_time = ET.SubElement(nav_area_ts, "gml:validTime")
            time_period = ET.SubElement(valid_time, "gml:TimePeriod")
            time_period.set("gml:id", f"tp_{uuid.uuid4().hex[:8]}")
            begin_pos = ET.SubElement(time_period, "gml:beginPosition")
            begin_pos.text = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
            end_pos = ET.SubElement(time_period, "gml:endPosition")
            end_pos.set("indeterminatePosition", "unknown")
            
            # Interpretation
            interpretation = ET.SubElement(nav_area_ts, "aixm:interpretation")
            interpretation.text = "BASELINE"
            
            # Designator
            designator = ET.SubElement(nav_area_ts, "aixm:designator")
            designator.text = "TOFPA_AOC_TypeA"
            
            # Type
            nav_type = ET.SubElement(nav_area_ts, "aixm:type")
            nav_type.text = "TAKEOFF_CLIMB_SURFACE"
            
            # Geometry
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                self._add_aixm_geometry(nav_area_ts, geom)

    def _add_aixm_reference_line(self, root, layer):
        """Add reference line as AIXM Curve"""
        import xml.etree.ElementTree as ET
        import uuid
        from datetime import datetime
        
        for feature in layer.getFeatures():
            # Create feature member
            feature_member = ET.SubElement(root, "gml:featureMember")
            curve = ET.SubElement(feature_member, "aixm:Curve")
            curve.set("gml:id", f"reference_line_{uuid.uuid4().hex[:8]}")
            
            # Add designator
            designator = ET.SubElement(curve, "aixm:designator")
            designator.text = "TOFPA_REFERENCE_LINE"
            
            # Geometry
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                self._add_aixm_geometry(curve, geom)

    def _add_aixm_geometry(self, parent, geometry):
        """Add geometry to AIXM element in GML format"""
        import xml.etree.ElementTree as ET
        
        # Transform to WGS84 for AIXM compliance
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(
            geometry.crs() if hasattr(geometry, 'crs') else QgsProject.instance().crs(),
            crs_4326,
            QgsProject.instance()
        )
        
        geom_4326 = QgsGeometry(geometry)
        geom_4326.transform(transform)
        
        if geometry.type() == QgsWkbTypes.PolygonGeometry:
            self._add_gml_surface(parent, geom_4326)
        elif geometry.type() == QgsWkbTypes.LineGeometry:
            self._add_gml_curve(parent, geom_4326)

    def _add_gml_surface(self, parent, geometry):
        """Add GML Surface geometry"""
        import xml.etree.ElementTree as ET
        
        geom_elem = ET.SubElement(parent, "aixm:geometryComponent")
        surface = ET.SubElement(geom_elem, "aixm:Surface")
        surface.set("gml:id", f"srf_{hash(str(geometry.asWkt())) & 0x7fffffff}")
        surface.set("srsName", "urn:ogc:def:crs:EPSG::4326")
        surface.set("srsDimension", "3")
        
        patches = ET.SubElement(surface, "gml:patches")
        polygon_patch = ET.SubElement(patches, "gml:PolygonPatch")
        
        # Exterior boundary
        exterior = ET.SubElement(polygon_patch, "gml:exterior")
        linear_ring = ET.SubElement(exterior, "gml:LinearRing")
        pos_list = ET.SubElement(linear_ring, "gml:posList")
        
        # Get coordinates
        if geometry.isMultipart():
            polygon = geometry.asMultiPolygon()[0][0]  # First polygon, exterior ring
        else:
            polygon = geometry.asPolygon()[0]  # Exterior ring
            
        coords = []
        for point in polygon:
            # AIXM uses lat,lon,alt order
            coords.extend([f"{point.y():.8f}", f"{point.x():.8f}", f"{point.z():.3f}" if point.is3D() else "0.000"])
        
        pos_list.text = " ".join(coords)

    def _add_gml_curve(self, parent, geometry):
        """Add GML Curve geometry"""
        import xml.etree.ElementTree as ET
        
        geom_elem = ET.SubElement(parent, "aixm:geometryComponent")
        curve = ET.SubElement(geom_elem, "aixm:Curve")
        curve.set("gml:id", f"crv_{hash(str(geometry.asWkt())) & 0x7fffffff}")
        curve.set("srsName", "urn:ogc:def:crs:EPSG::4326")
        curve.set("srsDimension", "3")
        
        segments = ET.SubElement(curve, "gml:segments")
        line_segment = ET.SubElement(segments, "gml:LineStringSegment")
        pos_list = ET.SubElement(line_segment, "gml:posList")
        
        # Get coordinates
        if geometry.isMultipart():
            line = geometry.asMultiPolyline()[0]  # First line
        else:
            line = geometry.asPolyline()
            
        coords = []
        for point in line:
            # AIXM uses lat,lon,alt order
            coords.extend([f"{point.y():.8f}", f"{point.x():.8f}", f"{point.z():.3f}" if point.is3D() else "0.000"])
        
        pos_list.text = " ".join(coords)
