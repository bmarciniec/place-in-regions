""" implementation of the interactor for the polygon input for a polygonal rebar placement"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_IFW_Input as AllplanIFW
from ScriptObjectInteractors.BaseScriptObjectInteractor import BaseScriptObjectInteractor
from TypeCollections.ModelEleList import ModelEleList

from .UvsTransformation import UvsTransformation


@dataclass
class PolygonalPlacementInteractorResult:
    """ Result of the placement polygon input"""

    elementary_polygons : list[AllplanGeo.Polygon2D] = field(default_factory=list)
    """Elementary quadrilaterals representing the placement zones.

    Each quadrilateral has 4 edges, from which 2 are parallel to the placed shape
    """


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
            norm_vector:         normal vector of the bending shape, that should be placed
        """

        self.interactor_result = interactor_result
        self.coord_input       = coord_input
        self.polygon_input     = None

        self.uvs_trans = UvsTransformation()
        """Transformation from/to UVS"""

        self.shape_nv = norm_vector
        """Normal vector of the bending shape to be placed"""

        self.input_result = self.PolygonAnalysisResult.INVALID_FOR_PREVIEW
        """Result of the placement polygon input"""

        self.sub_polygons: list[AllplanGeo.Polygon2D] =[]
        """List with elementary placement polygons"""


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

        input_result, sub_polygons = self.analyse_input_polygon(for_preview=False)

        if input_result == self.PolygonAnalysisResult.VALID:
            self.interactor_result.elementary_polygons = sub_polygons
            return BaseScriptObjectInteractor.OnCancelFunctionResult.CONTINUE_INPUT

        return BaseScriptObjectInteractor.OnCancelFunctionResult.CANCEL_INPUT


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

        self.input_result, self.sub_polygons = self.analyse_input_polygon(for_preview=True)

        self.draw_preview()

        if self.coord_input.IsMouseMove(mouse_msg):
            return True

        if self.coord_input.SelectElement(mouse_msg,pnt,msg_info,False,True,True):
            if (new_uvs := self.coord_input.GetSelectedElementAssocView()) != AllplanEleAdapter.AssocViewElementAdapter():
                self.uvs_trans = UvsTransformation(new_uvs)

        return True


    def draw_preview(self):
        """ Draw the preview"""

        if self.input_result == self.PolygonAnalysisResult.INVALID_FOR_PREVIEW:
            return

        preview_common_props = AllplanBaseEle.CommonProperties()
        if self.input_result == self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT:
            preview_common_props.Color = 6
        else:
            preview_common_props.Color = 4

        polygon_ele = ModelEleList(preview_common_props)
        polygon_ele.append_geometry_2d(self.sub_polygons)

        AllplanBaseEle.DrawElementPreview(self.polygon_input.GetInputViewDocument(),
                                          AllplanGeo.Matrix3D(), polygon_ele, True, None)

    def analyse_input_polygon(self, for_preview: bool = True) -> tuple[PolygonalPlacementInteractor.PolygonAnalysisResult, list[AllplanGeo.Polygon2D]]:
        """Analyses the input polygon

        The input polygon must consist of at least two vertical segments at the beginning and the end.

        Args:
            for_preview: whether to analyse the preview polygon (True) or the final input polygon (False)

        Returns:
            result of the analysis
            list of the elementary polygons
        """
        polygon = self.polygon_input.GetPreviewPolygon() if for_preview else self.polygon_input.GetPolygon()

        # flatten the polygon
        xy_projection = AllplanGeo.Matrix3D(1,0,0,0,
                                            0,1,0,0,
                                            0,0,0,0,
                                            0,0,0,1)
        polygon *= xy_projection

        if not polygon.IsValid():
            return (self.PolygonAnalysisResult.INVALID_FOR_PREVIEW, [AllplanGeo.Polygon2D()])

        # convert to 2D
        _, polygon = AllplanGeo.ConvertTo2D(polygon)

        # for some reason clockwise polygons are problematic
        # if that is the case, reverse the polygon
        if polygon.NormalizeNoThrow() != AllplanGeo.eGeometryErrorCode.eOK:
            polygon.Reverse()
        if polygon.NormalizeNoThrow() != AllplanGeo.eGeometryErrorCode.eOK:
            return (self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT, [polygon])

        # check, whether shape and placement polygon are coplanar
        local_placement_vec = self.shape_nv * self.uvs_trans.world_to_uvs
        local_placement_vec *= xy_projection

        if local_placement_vec.IsZero():
            return (self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT, [polygon])

        local_placement_vec.Normalize()

        global_to_local = AllplanGeo.Matrix3D()
        global_to_local.SetRotation(local_placement_vec, AllplanGeo.Vector3D(1,0,0))
        global_to_local = global_to_local.ReduceZDimension()

        local_to_global = AllplanGeo.Matrix2D(global_to_local)
        local_to_global.Reverse()

        local_polygon = AllplanGeo.Transform(polygon, global_to_local)

        # check, whether the placement polygon has exactly two vertical segments
        _, local_polygon_edges = local_polygon.GetSegments()
        start_end = [edge.StartPoint for edge in local_polygon_edges if (edge.GetVector() * AllplanGeo.Vector2D(0,1)).IsZero()]
        start_end.sort(key=lambda pnt: pnt.X)

        if len(start_end) != 2:
            return (self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT, [polygon])

        # split the polygon into elementary parts
        sub_polygons: list[AllplanGeo.Polygon2D] = []

        split_coords = [pnt.X for pnt in local_polygon.Points if start_end[0].X < pnt.X < start_end[1].X]
        split_coords.sort()

        for x_coord in split_coords:
            split_line = AllplanGeo.Polyline2D([AllplanGeo.Point2D(x_coord,-1e16), AllplanGeo.Point2D(x_coord,1e16)])

            _, _, local_left_polygon, local_right_polygon = AllplanGeo.Split(local_polygon, split_line, 1e-11, True)

            if local_left_polygon.Count() != 5:
                return (self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT, [polygon])

            sub_polygons.append(AllplanGeo.Transform(local_left_polygon, local_to_global))
            local_polygon = local_right_polygon

        if local_polygon.Count() != 5:
            return (self.PolygonAnalysisResult.INVALID_FOR_POLYGONAL_PLACEMENT, [polygon])

        sub_polygons.append(AllplanGeo.Transform(local_polygon, local_to_global))
        return (self.PolygonAnalysisResult.VALID, sub_polygons)
