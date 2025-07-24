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
from qgis.PyQt.QtCore import QCoreApplication, QVariant, Qt
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QFileDialog, QAction
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
                      QgsPoint, QgsField, QgsPolygon, QgsLineString, Qgis, 
                      QgsFillSymbol, QgsLineSymbol, QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem)

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
            self.iface.removeToolBarIcon(action)        # Remove the panel if it's open
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
            params['export_kmz']
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
                    level=Qgis.Critical                )
                return None

    def create_tofpa_surface(self, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, 
                            runway_layer_id, threshold_layer_id, use_selected_feature, export_kmz):
        """Create the TOFPA surface with the given parameters - ORIGINAL LOGIC"""
        
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
        pt_01D = new_geom.project(dD, azimuth)  # Project from threshold by CWY length in the direction of the flight
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
        
        # Export to KMZ if requested (include both surface and reference line)
        if export_kmz:
            layers_to_export = [v_layer, ref_layer]
            self.export_to_kmz(layers_to_export)
        
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