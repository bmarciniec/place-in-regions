""" implementation of the interactor for the polygon input
"""

from dataclasses import dataclass
from typing import Any

import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_BasisElements as AllplanBasisEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_IFW_Input as AllplanIFW
from ScriptObjectInteractors.BaseScriptObjectInteractor import BaseScriptObjectInteractor

from .UvsTransformation import UvsTransformation


@dataclass
class PolygonInteractorResult:
    """ implementation of the interactor result
    """

    input_polygon : AllplanGeo.Polygon3D = AllplanGeo.Polygon3D()
    uvs:            AllplanEleAdapter.AssocViewElementAdapter = AllplanEleAdapter.AssocViewElementAdapter()


class PolygonInteractor(BaseScriptObjectInteractor):
    """ implementation of the interactor for the polygon input
    """


    def __init__(self,
                 interactor_result  : PolygonInteractorResult,
                 coord_input        : AllplanIFW.CoordinateInput,
                 common_prop        : AllplanBaseEle.CommonProperties):
        """ Create the interactor

        Args:
            interactor_result:   result of the interactor
            coord_input:         API object for the coordinate input, element selection, ... in the Allplan view
            common_prop:         common properties of the polygon
            z_coord_input:       z coordinate input
            multi_polygon_input: multi polygon input
        """

        self.interactor_result   = interactor_result
        self.coord_input         = coord_input
        self.common_prop         = common_prop
        self.polygon_input       = None
        self.uvs                 = AllplanEleAdapter.AssocViewElementAdapter()


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
        uvs_transformation = UvsTransformation(self.uvs)
        result_polygon *= uvs_transformation.uvs_to_world

        # save the results
        self.interactor_result.input_polygon = result_polygon
        self.interactor_result.uvs = self.uvs

        return BaseScriptObjectInteractor.OnCancelFunctionResult.CONTINUE_INPUT if self.interactor_result.input_polygon.IsValid() else \
               BaseScriptObjectInteractor.OnCancelFunctionResult.CANCEL_INPUT


    def on_preview_draw(self):
        """ Handles the preview draw event
        """

        self.draw_preview(self.polygon_input.GetPreviewPolygon())


    def on_mouse_leave(self):
        """ Handles the mouse leave event
        """

        self.draw_preview(self.polygon_input.GetPolygon())


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

        self.draw_preview(self.polygon_input.GetPreviewPolygon())

        if self.coord_input.IsMouseMove(mouse_msg):
            return True

        if self.coord_input.SelectElement(mouse_msg,pnt,msg_info,False,True,True):

            if (new_uvs := self.coord_input.GetSelectedElementAssocView()) != AllplanEleAdapter.AssocViewElementAdapter():
                self.uvs = new_uvs
        return True


    def draw_preview(self,
                     polygon: AllplanGeo.Polygon3D):
        """ draw the preview

        Args:
            polygon: polygon
        """
        is_valid, polygon_2d = AllplanGeo.ConvertTo2D(polygon)

        if not is_valid:
            return

        polygon_ele = AllplanBasisEle.ModelElement2D(self.common_prop, polygon_2d)

        AllplanBaseEle.DrawElementPreview(self.polygon_input.GetInputViewDocument(),
                                          AllplanGeo.Matrix3D(), [polygon_ele], True, None)
