# -*- coding: utf-8 -*-

"""
/***************************************************************************
Name                 : RT MapServer Exporter
Description          : A plugin to export qgs project to mapfile
Date                 : Oct 21, 2012 
copyright            : (C) 2012 by Giuseppe Sucameli (Faunalia)
email                : brush.tyler@gmail.com

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

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *
from qgis.gui import *

from .ui.mapfileexportdlg_ui import Ui_MapfileExportDlg
import mapscript

from urlparse import parse_qs

_toUtf8 = lambda s: unicode(s).encode('utf8')

mmToPixelFactor = 3.77952755905 # pour 96 dpi = 38 dot/cm = 3.8 dot/mm


class MapfileExportDlg(QDialog, Ui_MapfileExportDlg):

    unitMap = {
        QGis.DecimalDegrees : mapscript.MS_DD,
        QGis.Meters : mapscript.MS_METERS, 
        QGis.Feet : mapscript.MS_FEET
    }

    onOffMap = {
        True : mapscript.MS_ON, 
        False : mapscript.MS_OFF
    }

    trueFalseMap = {
        True : mapscript.MS_TRUE, 
        False : mapscript.MS_FALSE
    }

    @classmethod
    def getLayerType(self, layer):
        if layer.type() == QgsMapLayer.RasterLayer:
            return mapscript.MS_LAYER_RASTER
        if layer.geometryType() == QGis.Point:
            return mapscript.MS_LAYER_POINT
        if layer.geometryType() == QGis.Line:
            return mapscript.MS_LAYER_LINE
        if layer.geometryType() == QGis.Polygon:
            return mapscript.MS_LAYER_POLYGON

    @classmethod
    def getLabelPosition(self, palLabel):
        if palLabel.yQuadOffset == 1:
            if palLabel.xQuadOffset == -1:
                return mapscript.MS_UL
            elif palLabel.xQuadOffset == 0:
                return mapscript.MS_UC
            elif palLabel.xQuadOffset == 1:
                return mapscript.MS_UR
        elif palLabel.yQuadOffset == 0:
            if palLabel.xQuadOffset == -1:
                return mapscript.MS_CL
            elif palLabel.xQuadOffset == 0:
                return mapscript.MS_CC
            elif palLabel.xQuadOffset == 1:
                return mapscript.MS_CR
        elif palLabel.yQuadOffset == -1:
            if palLabel.xQuadOffset == -1:
                return mapscript.MS_LL
            elif palLabel.xQuadOffset == 0:
                return mapscript.MS_LC
            elif palLabel.xQuadOffset == 1:
                return mapscript.MS_LR
        return mapscript.MS_AUTO


    def __init__(self, iface, parent=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.legend = self.iface.legendInterface()

        # hide map unit combo and label
        self.label4.hide()
        self.cmbMapUnits.hide()

        # setup the template table
        m = TemplateModel(self)
        for layer in self.legend.layers():
            m.append( layer )
        self.templateTable.setModel(m)
        d = TemplateDelegate(self)
        self.templateTable.setItemDelegate(d)

        # get the default title from the project
        title = QgsProject.instance().title()
        if title == "":
            title = QFileInfo( QgsProject.instance().fileName() ).completeBaseName()
        if title != "":
            self.txtMapName.setText( title )

	# add the last used mapfile
        self.loadProperties()

        # fill the image format combo
        self.cmbMapImageType.addItems( QStringList(["png", "gif", "jpeg", "svg", "GTiff"]) )

        QObject.connect( self.btnChooseFile, SIGNAL("clicked()"), self.selectMapFile )
        QObject.connect( self.btnChooseTemplate, SIGNAL("clicked()"), self.selectTemplateBody )
        QObject.connect( self.btnChooseTmplHeader, SIGNAL("clicked()"), self.selectTemplateHeader )
        QObject.connect( self.btnChooseTmplFooter, SIGNAL("clicked()"), self.selectTemplateFooter )


    def loadProperties(self):
        # load last used values
        settings = QSettings()

        lastUsedMapFile = settings.value("/rt_mapserver_exporter/lastUsedMapFile", "").toString()
        self.txtMapFilePath.setText( lastUsedMapFile )

        lastUsedTmpl = settings.value("/rt_mapserver_exporter/lastUsedTmpl", "").toString()
        self.txtTemplatePath.setText( lastUsedTmpl )

        lastUsedFontsFile = settings.value("/rt_mapserver_exporter/lastUsedFontsFile", "").toString()
        self.txtMapFontsetPath.setText( lastUsedFontsFile )

        lastUsedMapServerURL = settings.value("/rt_mapserver_exporter/lastUsedMapServerURL", "").toString()
        self.txtMapServerUrl.setText( lastUsedMapServerURL )

    def storeProperties(self):
        # store the last used map file properties
        settings = QSettings()

        settings.setValue("/rt_mapserver_exporter/lastUsedMapFile",  self.txtMapFilePath.text())
        settings.setValue("/rt_mapserver_exporter/lastUsedTmpl", self.txtTemplatePath.text())
        settings.setValue("/rt_mapserver_exporter/lastUsedFontsFile", self.txtMapFontsetPath.text())
        settings.setValue("/rt_mapserver_exporter/lastUsedMapServerURL", self.txtMapServerUrl.text())


    def selectMapFile(self):
        # ask for choosing where to store the map file
        filename = QFileDialog.getSaveFileName(self, "Select where to save the map file", self.txtMapFilePath.text(), "MapFile (*.map)")
        if filename == "":
            return

        # update the displayd path
        self.txtMapFilePath.setText( filename )

    def selectTemplateBody(self):
        self.selectTemplateFile( self.txtTemplatePath )

    def selectTemplateHeader(self):
        self.selectTemplateFile( self.txtTmplHeaderPath )

    def selectTemplateFooter(self):
        self.selectTemplateFile( self.txtTmplFooterPath )

    def selectTemplateFile(self, lineedit):
        # ask for choosing where to store the map file
        filename = QFileDialog.getOpenFileName(self, "Select the template file", lineedit.text(), "Template (*.html *.tmpl);;All files (*);;")
        if filename == "":
            return

        # update the path
        lineedit.setText( filename )


    def accept(self):
        # check user inputs
        if self.txtMapFilePath.text() == "":
            QMessageBox.warning(self, "RT MapServer Exporter", "Mapfile output path is required")
            return

        # create a new ms_map
        ms_map = mapscript.mapObj()
        ms_map.name = _toUtf8( self.txtMapName.text().replace(" ", "") )

        # map size
        (width, widthOk), (height, heightOk) = self.txtMapWidth.text().toInt(), self.txtMapHeight.text().toInt()
        if widthOk and heightOk:
            ms_map.setSize( width, height )

        # map units
        ms_map.units = self.unitMap[ self.canvas.mapUnits() ]
        if self.cmbMapUnits.currentIndex() >= 0:
            units, ok = self.cmbMapUnits.itemData( self.cmbMapUnits.currentIndex() ).toInt()
            if ok:
                ms_map.units = units

        # config options
        ms_map.setConfigOption("MS_ERRORFILE", "/tmp/ms_"+ ms_map.name +".log")

        # map extent
        extent = self.canvas.fullExtent()
        ms_map.extent.minx = extent.xMinimum()
        ms_map.extent.miny = extent.yMinimum()
        ms_map.extent.maxx = extent.xMaximum()
        ms_map.extent.maxy = extent.yMaximum()
        if self.canvas.mapRenderer().destinationCrs().authid() != "":
            ms_map.setProjection( "+init=" + _toUtf8( self.canvas.mapRenderer().destinationCrs().authid() ).lower() )
        else:
            ms_map.setProjection( _toUtf8( self.canvas.mapRenderer().destinationCrs().toProj4() ) )

        if self.txtMapShapePath.text() != "":
            ms_map.shapepath = _toUtf8( self.getMapShapePath() )

        # image section
        r,g,b,a = self.canvas.canvasColor().getRgb()
        ms_map.imagecolor.setRGB( r, g, b )    #255,255,255
        ms_map.setImageType( _toUtf8( self.cmbMapImageType.currentText() ) )
        ms_outformat = ms_map.getOutputFormatByName( ms_map.imagetype )
        ms_outformat.transparent = self.onOffMap[ True ]
        ms_map.transparent = mapscript.MS_TRUE

        # legend section
        #r,g,b,a = self.canvas.canvasColor().getRgb()
        #ms_map.legend.imageColor.setRgb( r, g, b )
        #ms_map.legend.status = mapscript.MS_ON
        #ms_map.legend.keysizex = 18
        #ms_map.legend.keysizey = 12
        #ms_map.legend.label.type = mapscript.MS_BITMAP
        #ms_map.legend.label.size = MEDIUM??
        #ms_map.legend.label.color.setRgb( 0, 0, 89 )
        #ms_map.legend.label.partials = self.trueFalseMap[ self.checkBoxPartials ]
        #ms_map.legend.label.force = self.trueFalseMap[ self.checkBoxForce ]
        #ms_map.legend.template = "[templatepath]"

        # web section
        ms_map.web.imagepath = _toUtf8( self.getWebImagePath() )
        ms_map.web.imageurl = _toUtf8( self.getWebImageUrl() )
        ms_map.web.temppath = _toUtf8( self.getWebTemporaryPath() )

        # web template
        ms_map.web.template = _toUtf8( self.getTemplatePath() )
        ms_map.web.header = _toUtf8( self.getTemplateHeaderPath() )
        ms_map.web.footer = _toUtf8( self.getTemplateFooterPath() )

        # map metadata
        if (QgsProject.instance().readBoolEntry( "WMSServiceCapabilities", "/", False )):
            ms_map.setMetaData( "ows_title", _toUtf8( QgsProject.instance().readEntry("WMSServiceTitle", "/", "")[0] ) )
            ms_map.setMetaData( "ows_abstract", _toUtf8( QgsProject.instance().readEntry("WMSServiceAbstract", "/", "")[0] ) )
            ms_map.setMetaData( "ows_contactorganization", _toUtf8( QgsProject.instance().readEntry("WMSContactOrganization", "/", "")[0] ) )
            ms_map.setMetaData( "ows_contactperson", _toUtf8( QgsProject.instance().readEntry("WMSContactPerson", "/", "")[0] ) )
            ms_map.setMetaData( "ows_contactelectronicmailaddress", _toUtf8( QgsProject.instance().readEntry("WMSContactMail", "/", "")[0] ) )
            ms_map.setMetaData( "ows_contactvoicetelephone", _toUtf8( QgsProject.instance().readEntry("WMSContactPhone", "/", "")[0] ) )
            ms_map.setMetaData( "ows_keywordlist", _toUtf8( QgsProject.instance().readListEntry("WMSKeywordList", "/") [0].join(",") ) )
            ms_map.setMetaData( "ows_accessconstraints", _toUtf8( QgsProject.instance().readEntry("WMSAccessConstraints", "/", "")[0] ) )
        else:
            ms_map.setMetaData( "ows_title", _toUtf8( self.txtMapName.text() ) )
        
        ms_map.setMetaData( "ows_onlineresource", _toUtf8( u"%s?map=%s" % (self.txtMapServerUrl.text(), self.txtMapFilePath.text()) ) )
        srsList = ["EPSG:4326"]
        srsList.append( _toUtf8( self.canvas.mapRenderer().destinationCrs().authid() ) )
        ms_map.setMetaData( "ows_srs", ' '.join(srsList) )
        ms_map.setMetaData( "ows_enable_request", "*" )
        ms_map.setMetaData( "wms_feature_info_mime_type", "text/html")

        for layer in self.legend.layers():
            # create a layer object
            ms_layer = mapscript.layerObj( ms_map )
            ms_layer.name = _toUtf8( layer.name().replace(" ", "") )
            ms_layer.type = self.getLayerType( layer )
            ms_layer.status = self.onOffMap[ self.legend.isLayerVisible( layer ) ]

            # layer extent
            extent = layer.extent()
            ms_layer.extent.minx = extent.xMinimum()
            ms_layer.extent.miny = extent.yMinimum()
            ms_layer.extent.maxx = extent.xMaximum()
            ms_layer.extent.maxy = extent.yMaximum()

            if layer.crs().authid() != "":
                ms_layer.setProjection( "+init=" + _toUtf8( layer.crs().authid() ).lower() )
            else:
                ms_layer.setProjection( _toUtf8( layer.crs().toProj4() ) )

            if layer.hasScaleBasedVisibility():
                ms_layer.minscaledenom = layer.minimumScale()
                ms_layer.maxscaledenom = layer.maximumScale()

            if layer.title() != "":
                ms_layer.setMetaData( "ows_title", _toUtf8(layer.title()))
            else:
                ms_layer.setMetaData( "ows_title", _toUtf8(layer.name()))

            if layer.abstract() != "":
                ms_layer.setMetaData( "ows_abstract",  _toUtf8(layer.abstract()))

            grPath = self.getGroupPath(layer)
            if grPath != "":
                ms_layer.setMetaData( "wms_layer_group", grPath)


            # layer connection
            if layer.providerType() == 'postgres':
                ms_layer.setConnectionType( mapscript.MS_POSTGIS, "" )
                uri = QgsDataSourceURI( layer.source() )
                ms_layer.connection = _toUtf8( uri.connectionInfo() )
                data = u"%s FROM %s" % ( uri.geometryColumn(), uri.quotedTablename() )
                #The keyColumn name is invalid with QGis 1.9dev
                if uri.keyColumn() != "":
                    data += u" USING UNIQUE %s" % uri.keyColumn()
                data += u" USING srid=%s" % uri.srid()
                if uri.sql() != "":
                  data += " FILTER (%s)" % uri.sql()
                ms_layer.data = _toUtf8( data )

            elif layer.providerType() == 'wms':
                ms_layer.setConnectionType( mapscript.MS_WMS, "" )
                q = parse_qs(_toUtf8(layer.source()), True)
                ms_layer.connection = q["url"][0]

                # loop thru wms sub layers
                wmsNames = []
                wmsStyles = []
                wmsLayerNames = q["layers"]
                wmsLayerStyles = q["styles"]
                for index in range(len(wmsLayerNames)): 
                    wmsNames.append( _toUtf8( wmsLayerNames[index] ) )
                    wmsStyles.append( _toUtf8( wmsLayerStyles[index] ) )

                # output SRSs
                srsList = []
                srsList.append( _toUtf8( layer.crs().authid() ) )

                # Create necessary wms metadata
                ms_layer.setMetaData( "ows_name", ','.join(wmsNames) )
                ms_layer.setMetaData( "wms_server_version", "1.1.1" )
                ms_layer.setMetaData( "ows_srs", ' '.join(srsList) )
                ms_layer.setMetaData( "wms_format", q["format"][0] )

            elif layer.providerType() == 'wfs':
                ms_layer.setConnectionType( mapscript.MS_WMS, "" )
                uri = QgsDataSourceURI( layer.source() )
                ms_layer.connection = _toUtf8( uri.uri() )

                # output SRSs
                srsList = []
                srsList.append( _toUtf8( layer.crs().authid() ) )

                # Create necessary wms metadata
                ms_layer.setMetaData( "ows_name", ms_layer.name )
                #ms_layer.setMetaData( "wfs_server_version", "1.1.1" )
                ms_layer.setMetaData( "ows_srs", ' '.join(srsList) )
           
            elif layer.providerType() == 'spatialite':
                ms_layer.setConnectionType( mapscript.MS_OGR, "" )
                uri = QgsDataSourceURI( layer.source() )
                ms_layer.connection = _toUtf8( uri.database() )    
                ms_layer.data = _toUtf8( uri.table() )    

            elif layer.providerType() == 'ogr':
                #ms_layer.setConnectionType( mapscript.MS_OGR, "" )
                ms_layer.data = _toUtf8( layer.source().split('|')[0] )    

            else:
                ms_layer.data = _toUtf8( layer.source() )    

            # set layer style
            if layer.type() == QgsMapLayer.RasterLayer:
                if hasattr(layer, 'renderer'):    # QGis >= 1.9
                    opacity = int( 100 *layer.renderer().opacity())
                else:
                    opacity = int( 100 * layer.getTransparency() / 255.0 )
                ms_layer.opacity = opacity

            else:
                # use a SLD file set the layer style
                tempSldFile = QTemporaryFile("rt_mapserver_exporter-XXXXXX.sld")
                tempSldFile.open()
                tempSldPath = tempSldFile.fileName()
                tempSldFile.close()

                # export the QGIS layer style to SLD file
                errMsg, ok = layer.saveSldStyle( tempSldPath )
                if not ok:
                    QgsMessageLog.logMessage( errMsg, "RT MapServer Exporter" )
                else:
                    # set the mapserver layer style from the SLD file
                    with open( unicode(tempSldPath), 'r' ) as fin:
                        sldContents = fin.read()
                    if mapscript.MS_SUCCESS != ms_layer.applySLD( sldContents, _toUtf8( layer.name() ) ):
                        QgsMessageLog.logMessage( u"Something went wrong applying the SLD style to the layer '%s'" % ms_layer.name, "RT MapServer Exporter" )
                    QFile.remove( tempSldPath )

                    # Conversion des unites du SLD
                    self.convertMapUnit(ms_layer)

		    # set layer labels
		    #XXX the following code MUST be removed when QGIS will 
		    # have SLD label support
		    palLayer = QgsPalLayerSettings()
		    palLayer.readFromLayer(layer)
		    if palLayer.enabled:
		            if not palLayer.isExpression:
		                ms_layer.labelitem = _toUtf8( palLayer.fieldName )    
		            else:
		                #XXX expressions won't be supported until 
		                # QGIS have SLD label support
		                pass

		            if palLayer.scaleMin > 0:
		                ms_layer.labelminscaledenom = palLayer.scaleMin
		            if palLayer.scaleMax > 0:
		                ms_layer.labelmaxscaledenom = palLayer.scaleMax

		            ms_label = mapscript.labelObj()

		            ms_label.type = mapscript.MS_TRUETYPE
		            ms_label.antialias = mapscript.MS_TRUE

                            if layer.geometryType() == QGis.Line:
                                 if palLayer.placementFlags & QgsPalLayerSettings.AboveLine:
                                      ms_label.position = mapscript.MS_UC
                                 elif palLayer.placementFlags & QgsPalLayerSettings.BelowLine:
                                      ms_label.position = mapscript.MS_LC
                                 elif palLayer.placementFlags & QgsPalLayerSettings.OnLine:
                                      ms_label.position = mapscript.MS_CC
                                 ms_label.offsety = int( mmToPixelFactor * palLayer.dist )
                            else:
		                 ms_label.position = self.getLabelPosition( palLayer )
		                 # TODO: convert offset to pixels
		                 ms_label.offsetx = int( mmToPixelFactor * palLayer.xOffset )
		                 ms_label.offsety = int( mmToPixelFactor * palLayer.yOffset )

                            if palLayer.placement == palLayer.Line:
                                ms_label.anglemode = mapscript.MS_AUTO
                            if palLayer.placement == palLayer.Curved:
                                ms_label.anglemode = mapscript.MS_FOLLOW
                            else:
		                ms_label.angle = palLayer.angleOffset

		            # set label font name, size and color
		            fontFamily = palLayer.textFont.family().replace(" ", "")
		            fontStyle = palLayer.textNamedStyle.replace(" ", "")
		            ms_label.font = _toUtf8( u"%s-%s" % (fontFamily, fontStyle) )    
		            if palLayer.textFont.pointSize() > 0:
                                # Facteur 0.75 a ete mis en place pour s'approcher du rendu Qgis
		                ms_label.size = palLayer.textFont.pointSize() * 0.75
		            r,g,b,a = palLayer.textColor.getRgb()
		            ms_label.color.setRGB( r, g, b )

                            r,g,b,a = palLayer.bufferColor.getRgb()
		            ms_label.outlinecolor.setRGB( r, g, b )
                            ms_label.outlinewidth = int( mmToPixelFactor * palLayer.bufferSize )

		            if palLayer.fontLimitPixelSize:
		                ms_label.minsize = palLayer.fontMinPixelSize
		                ms_label.maxsize = palLayer.fontMaxPixelSize
		            ms_label.wrap = _toUtf8( palLayer.wrapChar )    

		            ms_label.priority = palLayer.priority

		            # TODO: convert buffer size to pixels
		            # ms_label.buffer = int( mmToPixelFactor * palLayer.bufferSize )

		            if int( palLayer.minFeatureSize ) > 0:
		                # TODO: convert feature size from mm to pixels
		                ms_label.minfeaturesize = int( mmToPixelFactor * palLayer.minFeatureSize )

                            for n in range(0, ms_layer.numclasses):
                                ms_class = ms_layer.getClass(n)
                                ms_class.addLabel( ms_label )
		           # ms_class = mapscript.classObj()
		           # ms_class.addLabel( ms_label )
		           # ms_layer.insertClass( ms_class )
        

        # save the map file now!
        if mapscript.MS_SUCCESS != ms_map.save( _toUtf8( self.txtMapFilePath.text() )     ):
            return

        # Save GUI parameters
        self.storeProperties()

        # Most of the following code does not use mapscript because it asserts 
        # paths you supply exists, but this requirement is usually not meet on 
        # the QGIS client used to generate the mafile.

        # get the mapfile content as string so we can manipulate on it
        with open( unicode(self.txtMapFilePath.text()), 'r' ) as fin:
            # parts holds the content lines
            parts = QString(fin.read()).split(u"\n")
        partsContentChanged = False

        # retrieve the list of used font aliases searching for FONT keywords
        fonts = []
        searchFontRx = QRegExp("^\\s*FONT\\s+")
        for line in parts.filter( searchFontRx ):
            # get the font alias, remove quotes around it
            fontName = line.replace(searchFontRx, "")[1:-1]
            # remove spaces within the font name
            fontAlias = QString(fontName).replace(" ", "")

            # append the font alias to the font list
            if fontAlias not in fonts:
                fonts.append( fontAlias )

                # update the font alias in the mapfile
                # XXX: the following lines cannot be removed since the SLD file 
                # could refer a font whose name contains spaces. When SLD specs
                # ate clear on how to handle fonts than we'll think whether 
                # remove it or not. 
                replaceFontRx = QRegExp(u"^(\\s*FONT\\s+\")%s(\".*)$" % QRegExp.escape(fontName))
                parts.replaceInStrings(replaceFontRx, u"\\1%s\\2" % fontAlias)
                partsContentChanged = True

        # create the file containing the list of font aliases used in the 
        # mapfile
        if self.checkCreateFontFile.isChecked():
            fontPath = QFileInfo(self.txtMapFilePath.text()).dir().filePath(u"fonts.txt")
            with open( unicode(fontPath), 'w' ) as fout:
                for fontAlias in fonts:
                    fout.write( unicode(fontAlias) )

        # add the FONTSET keyword with the associated path
        if self.txtMapFontsetPath.text() != "":
            pos = parts.indexOf( QRegExp("^MAP$") )
            if pos >= 0:
                parts.insert( pos+1, u'  FONTSET "%s"' % self.txtMapFontsetPath.text() )
                partsContentChanged = True
            else:
                QgsMessageLog.logMessage( u"'FONTSET' keyword not added to the mapfile: unable to locate the 'WEB' keyword...", "RT MapServer Exporter" )

        # if mapfile content changed, store the file again at the same path
        if partsContentChanged:
            with open( unicode(self.txtMapFilePath.text()), 'w' ) as fout:
                fout.write( unicode( parts.join(u"\n") ) )

        # XXX for debugging only: let's have a look at the map result! :)
        # XXX it works whether the file pointed by the fontset contains ALL the 
        # aliases of fonts referred from the mapfile.
        #ms_map = mapscript.mapObj( unicode( self.txtMapFilePath.text() ) )
        #ms_map.draw().save( _toUtf8( self.txtMapFilePath.text() + ".png" )    , ms_map )

        QDialog.accept(self)


    def generateTemplate(self):
        tmpl = u""

        if self.getTemplateHeaderPath() == "":
            tmpl += u'''<!-- MapServer Template -->
<html>
  <head>
    <title>%s</title>
  </head>
  <body>
''' % self.txtMapName.text()

        for lid, orientation in self.templateTable.model().getObjectIter():
            layer = QgsMapLayerRegistry.instance().mapLayer( lid.toString() )
            if not layer or layer.type() == QgsMapLayer.RasterLayer:
                continue

            # define the template file content
            tmpl += '[resultset layer="%s"]\n' % layer.id()

            layerTitle = layer.title() if layer.title() != "" else layer.name()
            tmpl += u'<b>"%s"</b>\n' % layerTitle

            tmpl += '<table class="idtmplt_tableclass">\n'

            if orientation == Qt.Horizontal:
                tmpl += '  <tr class="idtmplt_trclass_1h">\n'
                for n in range(0, layer.dataProvider().fields().count()):
                    fld = layer.dataProvider().fields().field(n)
                    fldDescr = fld.comment() if fld.comment() != "" else layer.attributeDisplayName(n)
                    tmpl += u'    <td class="idtmplt_tdclass_1h">"%s"</td>\n' % fldDescr
                tmpl += '</tr>\n'

                tmpl += '[feature limit=20]\n'

                tmpl += '  <tr class="idtmplt_trclass_2h">\n'
                for fld in layer.dataProvider().fields().toList():
                    fldDescr = fld.comment() if fld.comment() != "" else fld.name()
                    tmpl += u'    <td class="idtmplt_tdclass_2h">[item name="%s"]</td>\n' % fld.name()
                tmpl += '  </tr>\n'

                tmpl += '[/feature]\n'

            else:
                for fld in layer.dataProvider().fields().toList():
                    tmpl += '  <tr class="idtmplt_trclass_v">\n'

                    fldDescr = fld.comment() if fld.comment() != "" else fld.name()
                    tmpl += u'    <td class="idtmplt_tdclass_1v">"%s"</td>\n' % fldDescr

                    tmpl += '[feature limit=20]\n'
                    tmpl += u'    <td class="idtmplt_tdclass_2v">[item name="%s"]</td>\n' % fld.name()
                    tmpl += '[/feature]\n'

                    tmpl += '  </tr>\n'

            tmpl += '</table>\n'

            tmpl += '[/resultset]\n'
            tmpl += '<hr>\n'


        if self.getTemplateFooterPath() == "":
            tmpl += '''  </body>
</html>'''

        return tmpl

    def getTemplatePath(self):
        if self.checkTmplFromFile.isChecked():
            return self.txtTemplatePath.text() # "[templatepath]"

        elif self.checkGenerateTmpl.isChecked():
            # generate the template for layers
            tmplContent = self.generateTemplate()
            # store the template alongside the mapfile
            tmplPath = self.txtMapFilePath.text() + ".html.tmpl"
            with open( unicode(tmplPath), 'w' ) as fout:
                fout.write( tmplContent )
            return tmplPath

    def getTemplateHeaderPath(self):
        return self.txtTmplHeaderPath.text()

    def getTemplateFooterPath(self):
        return self.txtTmplFooterPath.text()

    def getMapShapePath(self):
        return self.txtMapShapePath.text()

    def getWebImagePath(self):
        return self.txtWebImagePath.text() #"/tmp/"

    def getWebImageUrl(self):
        return self.txtWebImageUrl.text() #"/tmp/"

    def getWebTemporaryPath(self):
        return self.txtWebTempPath.text() #"/tmp/"

    def getGroupPath(self, ms_layer):
        groupLayerRelationShip = self.iface.legendInterface().groupLayerRelationship()
        iterStr = ms_layer.id()
        path = [];
        mustContinue = True
        while mustContinue :
             mustContinue = False
	     for group in groupLayerRelationShip :
                  if (iterStr in group[1]):
                      path.insert(0,_toUtf8(group[0]))
                      iterStr = group[0]
                      mustContinue = True
                      break
        aggrPath = '/'.join(path)
        if aggrPath != '':
             return '/' + aggrPath
        else:
             return ''

    def convertMapUnit(self, ms_layer):
        for n in range(0, ms_layer.numclasses):
            ms_class = ms_layer.getClass(n)
            for m in range(0, ms_class.numstyles):
                ms_style = ms_class.getStyle(m)
		ms_style.width *= mmToPixelFactor
        return


class TemplateDelegate(QItemDelegate):
    """ delegate with some special item editors """

    def createEditor(self, parent, option, index):
        # special combobox for orientation
        if index.column() == 1:
            cbo = QComboBox(parent)
            cbo.setEditable(False)
            cbo.setFrame(False)
            for val, txt in TemplateModel.ORIENTATIONS.iteritems():
                cbo.addItem(txt, QVariant(val))
            return cbo
        return QItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        """ load data from model to editor """
        m = index.model()
        if index.column() == 1:
            val = m.data(index, Qt.UserRole).toInt()[0]
            editor.setCurrentIndex( editor.findData(val) )
        else:
            # use default
            QItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        """ save data from editor back to model """
        if index.column() == 1:
            val = editor.itemData(editor.currentIndex()).toInt()[0]
            model.setData(index, QVariant(TemplateModel.ORIENTATIONS[val]))
            model.setData(index, QVariant(val), Qt.UserRole)
        else:
            # use default
            QItemDelegate.setModelData(self, editor, model, index)

class TemplateModel(QStandardItemModel):

    ORIENTATIONS = { Qt.Horizontal : u"Horizontal", Qt.Vertical : u"Vertical" }

    def __init__(self, parent=None):
        self.header = ["Layer name", "Orientation"]
        QStandardItemModel.__init__(self, 0, len(self.header), parent)

    def append(self, layer):
        rowdata = []

        item = QStandardItem( unicode(layer.name()) )
        item.setFlags( item.flags() & ~Qt.ItemIsEditable )
        rowdata.append( item )

        item = QStandardItem( TemplateModel.ORIENTATIONS[Qt.Horizontal] )
        item.setFlags( item.flags() | Qt.ItemIsEditable )
        rowdata.append( item )

        self.appendRow( rowdata )

        row = self.rowCount()-1
        self.setData(self.index(row, 0), QVariant(layer.id()), Qt.UserRole)
        self.setData(self.index(row, 1), QVariant(Qt.Horizontal), Qt.UserRole)

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return QVariant(self.header[section])
        return QVariant()

    def getObject(self, row):
        lid = self.data(self.index(row, 0), Qt.UserRole)
        orientation = self.data(self.index(row, 1), Qt.UserRole)
        return (lid, orientation)

    def getObjectIter(self):
        for row in range(self.rowCount()):
            yield self.getObject(row)

