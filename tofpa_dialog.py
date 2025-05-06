# -*- coding: utf-8 -*-
"""
/***************************************************************************
 TOFPADialog
                                 A QGIS plugin
 Takeoff and Final Approach Analysis Tool
                             -------------------
        begin                : 2024-04-14
        git sha              : $Format:%H$
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

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLabel, 
                                QDoubleSpinBox, QDialogButtonBox, QComboBox, 
                                QCheckBox, QGroupBox, QHBoxLayout, QPushButton)
from qgis.core import QgsProject, QgsMapLayerProxyModel

class TOFPADialog(QDialog):
    def __init__(self, parent=None, iface=None):
        super(TOFPADialog, self).__init__(parent)
        self.setWindowTitle("TOFPA - Takeoff and Final Approach")
        self.setMinimumWidth(500)
        self.iface = iface
        
        # Make the dialog non-blocking
        self.setWindowModality(Qt.NonModal)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Add title
        title_label = QLabel("TOFPA Parameters")
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Add description
        desc_label = QLabel("Take Off Climb Surface considering 15° course changes in night IMC or VMC conditions")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc_label)
        
        # Layer selection group
        layer_group = QGroupBox("Layer Selection")
        layer_layout = QFormLayout()
        
        # Runway layer selection
        self.runway_layer_combo = QComboBox()
        self.runway_layer_combo.setMinimumWidth(250)
        
        # Threshold layer selection
        self.threshold_layer_combo = QComboBox()
        self.threshold_layer_combo.setMinimumWidth(250)
        
        # Populate layer combos and set active layer as default
        active_layer = self.iface.activeLayer() if self.iface else None
        active_layer_id = active_layer.id() if active_layer else None
        
        for i, layer in enumerate(QgsProject.instance().mapLayers().values()):
            if layer.type() == 0:  # Vector layer
                self.runway_layer_combo.addItem(layer.name(), layer.id())
                self.threshold_layer_combo.addItem(layer.name(), layer.id())
                
                # Seleccionar la capa activa por defecto
                if active_layer_id and layer.id() == active_layer_id:
                    self.runway_layer_combo.setCurrentIndex(i)
                    self.threshold_layer_combo.setCurrentIndex(i)
        
        layer_layout.addRow("Runway Layer:", self.runway_layer_combo)
        layer_layout.addRow("Threshold Layer:", self.threshold_layer_combo)
        
        # Use selected feature checkbox
        self.use_selected_feature_check = QCheckBox("Use selected feature (if multiple features exist)")
        self.use_selected_feature_check.setChecked(True)
        layer_layout.addRow("", self.use_selected_feature_check)
        
        layer_group.setLayout(layer_layout)
        layout.addWidget(layer_group)
        
        # Create form layout for parameters
        form_group = QGroupBox("Surface Parameters")
        form_layout = QFormLayout()
        
        # Width parameters - Increased maximums for aviation
        self.width_tofpa_spin = QDoubleSpinBox()
        self.width_tofpa_spin.setMinimum(10)
        self.width_tofpa_spin.setMaximum(3000)  # Increased from 1000 to 3000
        self.width_tofpa_spin.setValue(180)
        self.width_tofpa_spin.setSuffix(" m")
        self.width_tofpa_spin.setDecimals(2)  # More precision
        form_layout.addRow("Initial Width:", self.width_tofpa_spin)
        
        self.max_width_tofpa_spin = QDoubleSpinBox()
        self.max_width_tofpa_spin.setMinimum(100)
        self.max_width_tofpa_spin.setMaximum(15000)  # Increased from 5000 to 15000
        self.max_width_tofpa_spin.setValue(1800)
        self.max_width_tofpa_spin.setSuffix(" m")
        self.max_width_tofpa_spin.setDecimals(2)  # More precision
        form_layout.addRow("Maximum Width:", self.max_width_tofpa_spin)
        
        # Clearway length - Increased maximum for aviation
        self.cwy_length_spin = QDoubleSpinBox()
        self.cwy_length_spin.setMinimum(0)
        self.cwy_length_spin.setMaximum(10000)  # Increased from 5000 to 10000
        self.cwy_length_spin.setValue(0)
        self.cwy_length_spin.setSuffix(" m")
        self.cwy_length_spin.setDecimals(2)  # More precision
        form_layout.addRow("Clearway Length:", self.cwy_length_spin)
        
        # Elevation parameters - Increased maximums for aviation
        self.z0_spin = QDoubleSpinBox()
        self.z0_spin.setMinimum(-1000)
        self.z0_spin.setMaximum(10000)  # Increased from 5000 to 10000
        self.z0_spin.setValue(0)
        self.z0_spin.setSuffix(" m")
        self.z0_spin.setDecimals(2)  # More precision
        form_layout.addRow("Initial Elevation (Z0):", self.z0_spin)
        
        self.ze_spin = QDoubleSpinBox()
        self.ze_spin.setMinimum(-1000)
        self.ze_spin.setMaximum(10000)  # Increased from 5000 to 10000
        self.ze_spin.setValue(0)
        self.ze_spin.setSuffix(" m")
        self.ze_spin.setDecimals(2)  # More precision
        form_layout.addRow("End Elevation (ZE):", self.ze_spin)
        
        # Direction selection has been removed as requested by the client
        # Always using Start (s=0) direction
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Export options
        export_group = QGroupBox("Export Options")
        export_layout = QVBoxLayout()
        
        # KMZ export option
        self.export_kmz_check = QCheckBox("Export to KMZ (for Google Earth)")
        self.export_kmz_check.setChecked(False)
        export_layout.addWidget(self.export_kmz_check)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        # Add note about selection
        note_label = QLabel("Note: Make sure to select features in the chosen layers before running if 'Use selected feature' is checked.")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)
        
        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def get_parameters(self):
        """Get the parameters from the dialog"""
        params = {
            'width_tofpa': self.width_tofpa_spin.value(),
            'max_width_tofpa': self.max_width_tofpa_spin.value(),
            'cwy_length': self.cwy_length_spin.value(),
            'z0': self.z0_spin.value(),
            'ze': self.ze_spin.value(),
            's': 0,  # Fixed to Start (s=0) as requested by client
            'runway_layer_id': self.runway_layer_combo.currentData(),
            'threshold_layer_id': self.threshold_layer_combo.currentData(),
            'use_selected_feature': self.use_selected_feature_check.isChecked(),
            'export_kmz': self.export_kmz_check.isChecked()
        }
        return params