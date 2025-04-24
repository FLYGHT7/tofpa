# -*- coding: utf-8 -*-
"""
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
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QDoubleSpinBox, QDialogButtonBox

class TOFPADialog(QDialog):
    def __init__(self, parent=None):
        super(TOFPADialog, self).__init__(parent)
        self.setWindowTitle("TOFPA - Takeoff and Final Approach")
        self.setMinimumWidth(400)
        
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
        
        # Create form layout for parameters
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
        
        # Add form layout to main layout
        layout.addLayout(form_layout)
        
        # Add note about selection
        note_label = QLabel("Note: Make sure to select a runway feature in a layer with 'runway' in its name and a threshold point in the active layer before running.")
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
            's': 0  # Siempre usar s=0 (Start) como mencionó el cliente
        }
        return params