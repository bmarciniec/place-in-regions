""" implementation of the interactor for the polygon input
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_BasisElements as AllplanBasisEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_IFW_Input as AllplanIFW
from ScriptObjectInteractors.BaseScriptObjectInteractor import BaseScriptObjectInteractor

from .UvsTransformation import UvsTransformation


@dataclass
class PolygonalPlacementInteractorResult:
    """ implementation of the interactor result
    """

    input_polygon : AllplanGeo.Polygon3D = AllplanGeo.Polygon3D()


class PolygonalPlacementInteractor(BaseScriptObjectInteractor):
    """ implementation of the interactor for the polygon input
    """
    class PolygonAnalysisResult(IntEnum):
        """Result of the input polygon analysis"""
        INVALID_FOR_PREVIEW = 0
        """Polygon is not valid, even to be previewed"""
        INVALID_FOR_POLYGONAL_PLACEMENT = 1
        """Polygon is valid to be previewed, but not to be used as polygonal placement"""
        VALID = 2
        """Polygon is valid to be used as polygonal placement"""

    def __init__(self,
                 interactor_result  : PolygonalPlacementInteractorResult,
                 coord_input        : AllplanIFW.CoordinateInput,
                 norm_vector        : AllplanGeo.Vector3D):
        """ Create the interactor

        Args:
            interactor_result:   result of the interactor
            coord_input:         API object for the coordinate input, element selection, ... in the Allplan view
            common_prop:         common properties of the polygon
            norm_vector:         normal vector of the bending shape, that should be placed
        """

        self.interactor_result   = interactor_result
        self.coord_input         = coord_input
        self.polygon_input       = None
        self.uvs_trans           = UvsTransformation()
        self.shape_nv            = norm_vector
        """Normal vector of the bending shape to be placed"""


    def start_input(self,
                    coord_input: AllplanIFW.CoordinateInput):
        """ start the input

        Args:
            coord_input: API object for the coordinate input, element selection, ... in the Allplan view
        """

        self.polygon_input = AllplanIFW.PolygonInput(coord_input, False, False)


    def on_cancel_function(self) -> BaseScriptObjectInteractor.OnCancelFunctionResult:
        """ Handles the cancel function event (e.g. by ESC, ...)

        Returns:
            True/False for success.
        """
        # flatten the polygon
        result_polygon = self.polygon_input.GetPolygon()
        xy_projection = AllplanGeo.Matrix3D(1,0,0,0,
                                            0,1,0,0,
                                            0,0,0,0,
                                            0,0,0,1)
        result_polygon *= xy_projection

        # trasform the polygon from UVS to global coordinate system
        result_polygon *= self.uvs_trans.uvs_to_world

        # save the results
        self.interactor_result.input_polygon = result_polygon

        return BaseScriptObjectInteractor.OnCancelFunctionResult.CONTINUE_INPUT if self.interactor_result.input_polygon.IsValid() else \
               BaseScriptObjectInteractor.OnCancelFunctionResult.CANCEL_INPUT


    def on_preview_draw(self):
        """ Handles the preview draw event
        """

        self.draw_preview()


    def on_mouse_leave(self):
        """ Handles the mouse leave event
        """

        self.draw_preview()


    def process_mouse_msg(self,
                          mouse_msg: int,
                          pnt      : AllplanGeo.Point2D,
                          msg_info : Any) -> bool:
        """ Process the mouse message event

        Args:
            mouse_msg: mouse message ID
            pnt:       input point in Allplan view coordinates
            msg_info:  additional mouse message info

        Returns:
            True/False for success.
        """

        self.polygon_input.ExecuteInput(mouse_msg, pnt, msg_info)

        self.draw_preview()

        if self.coord_input.IsMouseMove(mouse_msg):
            return True

        if self.coord_input.SelectElement(mouse_msg,pnt,msg_info,False,True,True):
            if (new_uvs := self.coord_input.GetSelectedElementAssocView()) != AllplanEleAdapter.AssocViewElementAdapter():
                self.uvs_trans = UvsTransformation(new_uvs)

        return True


    def draw_preview(self):
        """ draw the preview

        Args:
            polygon: polygon
        """
        analysis_result = self.analyse_input_polygon()

        if analysis_result == self.PolygonAnalysisResult.INVALID_FOR_PREVIEW:
            return

        preview_common_props = AllplanBaseEle.CommonProperties()
        if analysis_result == self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT:
            preview_common_props.Color = 6
        else:
            preview_common_props.Color = 4

        _, polygon = AllplanGeo.ConvertTo2D(self.polygon_input.GetPreviewPolygon())
        polygon_ele = AllplanBasisEle.ModelElement2D(preview_common_props, polygon)

        AllplanBaseEle.DrawElementPreview(self.polygon_input.GetInputViewDocument(),
                                          AllplanGeo.Matrix3D(), [polygon_ele], True, None)

    def analyse_input_polygon(self) -> PolygonalPlacementInteractor.PolygonAnalysisResult:
        """Analyses the input polygon"""

        polygon = self.polygon_input.GetPreviewPolygon()

        # flatten the polygone
        xy_projection = AllplanGeo.Matrix3D(1,0,0,0,
                                            0,1,0,0,
                                            0,0,0,0,
                                            0,0,0,1)
        polygon *= xy_projection

        if not polygon.IsValid():
            return self.PolygonAnalysisResult.INVALID_FOR_PREVIEW

        # check, whether shape and placement polygon
        local_shape_nv = self.shape_nv * self.uvs_trans.world_to_uvs
        local_shape_nv *= xy_projection

        if local_shape_nv.IsZero():
            print("Placement polygon and shape are coplanar!!!!")
            return self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT

        local_shape_nv.Normalize()
        uvs_to_shape = AllplanGeo.Matrix3D()
        uvs_to_shape.SetRotation(local_shape_nv,AllplanGeo.Vector3D(1,0,0))

        polygon *= uvs_to_shape

        heights_list = []

        for edge in polygon.GetLines():
            edge_vec = edge.GetVector()

            if not edge_vec.Project(AllplanGeo.Vector3D(1,0,0)).IsZero():
                continue

            heights_list.append((edge.StartPoint.X, AllplanGeo.CalcLength(edge)))

        if len(heights_list) != 2:
            return self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT

        return self.PolygonAnalysisResult.VALID