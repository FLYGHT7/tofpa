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
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.core import (QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, 
                      QgsPoint, QgsField, QgsPolygon, QgsLineString, Qgis, 
                      QgsFillSymbol, QgsVectorFileWriter, QgsCoordinateTransform,
                      QgsCoordinateReferenceSystem)

import os.path
from math import *

# Import the dialog
from .tofpa_dialog import TOFPADialog

class TOFPA:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.
        
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&TOFPA')
        
        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None
        
        # Store dialog instance
        self.dlg = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.
        
        :param message: String for translation.
        :type message: str, QString
        
        :returns: Translated version of message.
        :rtype: QString
        """
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
        """Add a toolbar icon to the toolbar.
        
        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str
        
        :param text: Text that should be shown in menu items for this action.
        :type text: str
        
        :param callback: Function to be called when the action is triggered.
        :type callback: function
        
        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool
        
        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool
        
        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool
        
        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str
        
        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget
        
        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.
        
        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'TOFPA'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&TOFPA'),
                action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """Run method that performs all the real work"""
        
        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = TOFPADialog(self.iface.mainWindow(), self.iface)
            self.dlg.accepted.connect(self.on_dialog_accepted)
        
        # Show the dialog
        self.dlg.show()

    def on_dialog_accepted(self):
        """Handle the dialog's accepted signal"""
        # Get parameters from dialog
        params = self.dlg.get_parameters()
        
        # Create the TOFPA surface
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

    def create_tofpa_surface(self, width_tofpa, max_width_tofpa, cwy_length, z0, ze, s, 
                            runway_layer_id, threshold_layer_id, use_selected_feature, export_kmz):
        """Create the TOFPA surface with the given parameters"""
        
        # Calculate s2 based on s
        if s == -1:
            s2 = 180
        else:
            s2 = 0
        
        map_srid = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Get runway layer by ID
        runway_layer = QgsProject.instance().mapLayer(runway_layer_id)
        if not runway_layer:
            self.iface.messageBar().pushMessage("Error", "Selected runway layer not found!", level=Qgis.Critical)
            return False
        
        # Get runway feature
        if use_selected_feature and runway_layer.selectedFeatureCount() > 0:
            selection = runway_layer.selectedFeatures()
        else:
            # If no selection or not using selection, use all features
            selection = list(runway_layer.getFeatures())
        
        if not selection:
            self.iface.messageBar().pushMessage("Error", "No runway features found in the selected layer!", level=Qgis.Critical)
            return False
        
        # Get runway geometry
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (z0-ze)/rwy_length if rwy_length > 0 else 0
        print(f"Runway length: {rwy_length}")
        
        # Get the azimuth of the line
        for feat in selection:
            geom = feat.geometry().asPolyline()
            # Verificar que el índice es válido
            if len(geom) <= abs(s):
                self.iface.messageBar().pushMessage("Error", "Runway geometry is too short for the selected direction!", level=Qgis.Critical)
                return False
                
            start_point = QgsPoint(geom[-1-s])
            end_point = QgsPoint(geom[s])
            angle0 = start_point.azimuth(end_point)
            back_angle0 = angle0+180
        
        # Initial true azimuth data
        azimuth = angle0+s2
        bazimuth = azimuth+180
        
        # Get the threshold point from selected layer
        threshold_layer = QgsProject.instance().mapLayer(threshold_layer_id)
        if not threshold_layer:
            self.iface.messageBar().pushMessage("Error", "Selected threshold layer not found!", level=Qgis.Critical)
            return False
        
        # Get threshold feature
        if use_selected_feature and threshold_layer.selectedFeatureCount() > 0:
            selection = threshold_layer.selectedFeatures()
        else:
            # If no selection or not using selection, use all features
            selection = list(threshold_layer.getFeatures())
        
        if not selection:
            self.iface.messageBar().pushMessage("Error", "No threshold features found in the selected layer!", level=Qgis.Critical)
            return False
        
        # Get threshold point
        for feat in selection:
            new_geom = QgsPoint(feat.geometry().asPoint())
            new_geom.addZValue(z0)
        
        list_pts = []
        
        # Origin
        pt_0d = new_geom
        
        # Distance for surface start
        if cwy_length == 0:
            dd = 0  # there is a condition to use the runway strip to analyze
        else:
            dd = cwy_length
        
        # Calculate all points for the TOFPA surface
        pt_01d = new_geom.project(dd, bazimuth)
        pt_01d.setZ(ze)
        pt_01dl = pt_01d.project(width_tofpa/2, bazimuth+90)
        pt_01dr = pt_01d.project(width_tofpa/2, bazimuth-90)
        
        # Distance to reach maximum width
        pt_02d = pt_01d.project(((max_width_tofpa/2-width_tofpa/2)/0.125), bazimuth)
        pt_02d.setZ(ze+((max_width_tofpa/2-width_tofpa/2)/0.125)*0.012)
        pt_02dl = pt_02d.project(max_width_tofpa/2, bazimuth+90)
        pt_02dr = pt_02d.project(max_width_tofpa/2, bazimuth-90)
        
        # Distance to end of TakeOff Climb Surface
        pt_03d = pt_01d.project(10000, bazimuth)
        pt_03d.setZ(ze+10000*0.012)
        pt_03dl = pt_03d.project(max_width_tofpa/2, bazimuth+90)
        pt_03dr = pt_03d.project(max_width_tofpa/2, bazimuth-90)
        
        list_pts.extend((pt_0d, pt_01d, pt_01dl, pt_01dr, pt_02d, pt_02dl, pt_02dr, pt_03d, pt_03dl, pt_03dr))
        
        # Creation of the Take Off Climb Surfaces
        # Create memory layer
        v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "RWY_TOFPA_AOC_TypeA", "memory")
        id_field = QgsField('ID', QVariant.String)
        name_field = QgsField('SurfaceName', QVariant.String)
        v_layer.dataProvider().addAttributes([id_field])
        v_layer.dataProvider().addAttributes([name_field])
        v_layer.updateFields()
        
        # Take Off Climb Surface Creation
        surface_area = [pt_03dr, pt_03dl, pt_02dl, pt_01dl, pt_01dr, pt_02dr]
        pr = v_layer.dataProvider()
        seg = QgsFeature()
        seg.setGeometry(QgsPolygon(QgsLineString(surface_area), rings=[]))
        seg.setAttributes([13, 'TOFPA AOC Type A'])
        pr.addFeatures([seg])
        
        # Load PolygonZ Layer to map canvas
        QgsProject.instance().addMapLayers([v_layer])
        
        # Change style of layer - Fixed to ensure consistent symbology
        symbol = QgsFillSymbol.createSimple({
            'color': '128,128,128,102',  # Grey with 40% opacity (102/255)
            'outline_color': '0,0,0,255',
            'outline_width': '0.5'
        })
        v_layer.renderer().setSymbol(symbol)
        v_layer.triggerRepaint()
        
        # Export to KMZ if requested
        if export_kmz:
            self.export_to_kmz(v_layer)
        
        # Zoom to layer
        v_layer.selectAll()
        canvas = self.iface.mapCanvas()
        canvas.zoomToSelected(v_layer)
        v_layer.removeSelection()
        
        # Get canvas scale
        sc = canvas.scale()
        if sc < 20000:
            sc = 20000
        canvas.zoomScale(sc)
        
        return True
    
    def export_to_kmz(self, layer):
        """Export the layer to KMZ format for Google Earth"""
        # Verificar que la capa tiene características
        if layer.featureCount() == 0:
            self.iface.messageBar().pushMessage(
                "Error", 
                "No features to export in the layer", 
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
            return False  # User cancelled
        
        # Ensure file has .kmz extension
        if not file_path.lower().endswith('.kmz'):
            file_path += '.kmz'
        
        # Set up KML options
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "KML"
        options.layerName = layer.name()
        
        # KML uses EPSG:4326 (WGS84)
        crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
        options.ct = QgsCoordinateTransform(
            layer.crs(), 
            crs_4326, 
            QgsProject.instance()
        )
        
        # Write to KML first (will be converted to KMZ)
        temp_kml = file_path.replace('.kmz', '.kml')
        result = QgsVectorFileWriter.writeAsVectorFormatV2(
            layer,
            temp_kml,
            QgsProject.instance().transformContext(),
            options
        )
        
        if result[0] != QgsVectorFileWriter.NoError:
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to export to KML: {result[1]}", 
                level=Qgis.Critical
            )
            return False
        
        # Convert KML to KMZ (zip the KML file)
        import zipfile
        try:
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(temp_kml, os.path.basename(temp_kml))
            
            # Remove temporary KML file
            try:
                os.remove(temp_kml)
            except PermissionError:
                self.iface.messageBar().pushMessage(
                    "Warning", 
                    f"Could not delete temporary KML file: {temp_kml}", 
                    level=Qgis.Warning
                )
            
            self.iface.messageBar().pushMessage(
                "Success", 
                f"Exported to KMZ: {file_path}", 
                level=Qgis.Success
            )
            return True
            
        except PermissionError:
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Permission denied when creating KMZ file. Check folder permissions.", 
                level=Qgis.Critical
            )
            return False
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", 
                f"Failed to create KMZ file: {str(e)}", 
                level=Qgis.Critical
            )
            return False