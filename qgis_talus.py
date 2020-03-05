# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

#from PyQt5.QtCore import QVariant
from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterBand,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterCrs,
                       QgsCoordinateReferenceSystem,
                       QgsRasterBlock,
                       QgsFields,
                       QgsField,
                       QgsWkbTypes
                       )
from qgis import processing#, WKBPoint
import networkx as nx
from talus import morse
import pickle

class ExampleProcessingAlgorithm(QgsProcessingAlgorithm):
    """
    This is an implementation of topographical prominence via
    topological persistence using the Talus library.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    TARGET_CRS = 'TARGET_CRS'

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ExampleProcessingAlgorithm()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'persistence'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Morse Persistence')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Talus')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'talus'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Topographical Prominence on DEM")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterRasterLayer( #QgsProcessingParameterBand
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeRaster]
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )
        #parameterAsCrs
        self.addParameter(
            QgsProcessingParameterCrs(
                self.TARGET_CRS,
                self.tr('Target CRS')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        # The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.
        source = self.parameterAsRasterLayer(
            parameters,
            self.INPUT,
            context
        )

        # If source was not found, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        your_fields = QgsFields()
        your_fields.append(QgsField('prmnc', QVariant.Int))

        out_crs = self.parameterAsCrs(
            parameters,
            self.TARGET_CRS,
            context
        )

        print(out_crs)
        print(type(out_crs))
        print(dir(out_crs))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            your_fields,
            QgsWkbTypes.Type.Point,
            out_crs
        )

        # Send some information to the user
        feedback.pushInfo('CRS is {}'.format(source.crs().authid()))

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # Compute the number of steps to display within the progress bar and
        # get features from source

        provider = source.dataProvider()

        extent = provider.extent()

        rows = source.height()
        cols = source.width()

        width = cols
        height = rows

        imgraph = nx.Graph()


        block = provider.block(1, extent, cols, rows)

        total = rows * cols
        print(total)
        # test_values = set()

        nodes = []

        biggest_value = 0
        for x in range(width):
            for y in range(height):
                idx = x + width * y
                value = block.value(y, x)
                # test_values.add(value)
                if value > biggest_value:
                    biggest_value = value
                my_node = morse.MorseNode(identifier=idx, value=value)
                nodes.append(my_node)

                # if we're not on the leastmost column,
                if(x > 0):
                    # add edge of column left/less
                    neighbor_idx = (x - 1) + width * y
                    neighbor_value = block.value(y, (x - 1)) # imarray[y, (x - 1)]
                    neighbor_node = morse.MorseNode(identifier=neighbor_idx, value=neighbor_value)
                    imgraph.add_edge(my_node, neighbor_node)
                # if we're not on the maximum column,
                if(x < (width - 1)):
                    # add edge of column right/greater
                    neighbor_idx = (x + 1) + width * y
                    neighbor_value = block.value(y, (x + 1)) # imarray[y, (x + 1)]
                    neighbor_node = morse.MorseNode(identifier=neighbor_idx, value=neighbor_value)
                    imgraph.add_edge(my_node, neighbor_node)
                # if we're not on the leastmost row,
                if(y > 0):
                    # add edge of row above/less
                    neighbor_idx = x + width * (y - 1)
                    neighbor_value = block.value((y - 1), x) # imarray[(y - 1), x]
                    neighbor_node = morse.MorseNode(identifier=neighbor_idx, value=neighbor_value)
                    imgraph.add_edge(my_node, neighbor_node)
                # if we're not on the maxmimum row,
                if(y < (height - 1)):
                    # add edge of row below/greater
                    neighbor_idx = x + width * (y + 1)
                    neighbor_value = block.value((y + 1), x) # imarray[(y + 1), x]
                    neighbor_node = morse.MorseNode(identifier=neighbor_idx, value=neighbor_value)
                    imgraph.add_edge(my_node, neighbor_node)

        print("pickling graph")
        pickleF = open(('/Users/weshellman/test_nxgraph.pickle'), 'wb')
        pickle.dump(imgraph, pickleF)

        print("running persistence")
        result = morse.persistence(imgraph)
        # print(result.descending_complex.compute_cells_at_lifetime(0))
        for f in result.descending_complex.filtration:
            print(result.descending_complex.compute_cells_at_lifetime(f.lifetime))
        for f in result.descending_complex.filtration:
            print(f)


        # for x in range(width):
        #     for y in range(height):
        #         idx = x + width * y
        #         if result[idx] == float('inf'):
        #             # imarray[y, x] = infinity_replacement_value
        #             print('Found highest prominence at ' + str(x) + ', ' + str(y))
        #         # else:
        #             # imarray[y, x] = int(result[idx])

        raise QgsProcessingException('lol')

        # for current, feature in enumerate(features):
        #     # Stop the algorithm if cancel button has been clicked
        #     if feedback.isCanceled():
        #         break
        #
        #     # Add a feature in the sink
        #     sink.addFeature(feature, QgsFeatureSink.FastInsert)
        #
        #     # Update the progress bar
        #     feedback.setProgress(int(current * total))

        # To run another Processing algorithm as part of this algorithm, you can use
        # processing.run(...). Make sure you pass the current context and feedback
        # to processing.run to ensure that all temporary layer outputs are available
        # to the executed algorithm, and that the executed algorithm can send feedback
        # reports to the user (and correctly handle cancellation and progress reports!)
        # if False:
        #     buffered_layer = processing.run("native:buffer", {
        #         'INPUT': dest_id,
        #         'DISTANCE': 1.5,
        #         'SEGMENTS': 5,
        #         'END_CAP_STYLE': 0,
        #         'JOIN_STYLE': 0,
        #         'MITER_LIMIT': 2,
        #         'DISSOLVE': False,
        #         'OUTPUT': 'memory:'
        #     }, context=context, feedback=feedback)['OUTPUT']

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return {self.OUTPUT: dest_id}
