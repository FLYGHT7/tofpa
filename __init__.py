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

def classFactory(iface):
    """Load TOFPA class from file tofpa.py
    
    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .tofpa import TOFPA
    return TOFPA(iface)