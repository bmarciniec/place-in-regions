"""Module containing script object interactor for the line input and
related classes, e.g. data class for saving the input results"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, overload

import NemAll_Python_BaseElements as AllplanBaseElements
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_IFW_Input as AllplanIFW
from BaseScriptObject import BaseScriptObject
from ScriptObjectInteractors.BaseScriptObjectInteractor import BaseScriptObjectInteractor
from TypeCollections.GeometryTyping import CURVES
from TypeCollections.ModelEleList import ModelEleList


@dataclass
class LineInteractorResult:
    """ implementation of the line interactor result
    """

    input_line  : AllplanGeo.Line3D = AllplanGeo.Line3D()
    input_value : float = 0.0
    element     : AllplanEleAdapter.BaseElementAdapter = AllplanEleAdapter.BaseElementAdapter()


class LineInteractor(BaseScriptObjectInteractor):
    """ Implementation of the interactor for line input

    This script object interactor prompts the user for input a 3D line. The line can be
    """

    def __init__(self,
                 interactor_result  : LineInteractorResult,
                 is_first_input     : bool,
                 prompt             : str,
                 allow_pick_up      : bool                                          = False,
                 allow_input_in_uvs : bool                                          = False,
                 preview_function   : (Callable[[AllplanGeo.Line3D], list] | None)  = None,
                 default_input_value: (float | None)                                = None,
                 abscissa_element   : CURVES                                        = None,
                 ):
        """ initialize

        Args:
            interactor_result:   result of the interactor
            is_first_input:      is this the first input in an input sequence
            prompt:              prompt message shown in the dialog line
            allow_pick_up:       allow to pick up a line from an existing object
            allow_input_in_uvs:  allow to input the line in an unified view or section
            preview_function:    function for generating preview elements during the input
            default_input_value: default input value. If set to None, no input value field is provided.
            abscissa_element:    abscissa element for the point projection
        """
        self.interactor_result   = interactor_result
        self.is_first_input      = is_first_input
        self.prompt              = prompt
        self.allow_pick_up       = allow_pick_up
        self.allow_uvs_input     = allow_input_in_uvs
        self.preview_function    = preview_function
        self.default_input_value = default_input_value
        self.abscisssa_element   = abscissa_element

        self.start_point         = None
        self.uvs_transform       = self.UvsTransformation(AllplanEleAdapter.AssocViewElementAdapter())
        self.coord_input         = None

        if default_input_value is not None:
            self.interactor_result.input_value = default_input_value

    def start_input(self,
                    coord_input: AllplanIFW.CoordinateInput):
        """ Start the input of the line's start point

        Args:
            coord_input: API object for the coordinate input, element selection, ... in the Allplan view
        """
        self.coord_input = coord_input

        ident_mode = AllplanIFW.CoordinateInputMode(
            AllplanIFW.eIdentificationMode.eIDENT_POINT_ELEMENT if self.allow_pick_up else AllplanIFW.eIdentificationMode.eIDENT_POINT)


        if self.default_input_value is None:
            if self.is_first_input:
                self.coord_input.InitFirstPointInput(AllplanIFW.InputStringConvert(self.prompt),ident_mode)
            else:
                self.coord_input.InitNextPointInput(AllplanIFW.InputStringConvert(self.prompt),ident_mode)
        else:
            input_control = AllplanIFW.ValueInputControlData(AllplanIFW.eValueInputControlType.eCOORDINATE_EDIT,
                                                            self.default_input_value,
                                                            True, False)
            if self.is_first_input:
                self.coord_input.InitFirstPointValueInput(AllplanIFW.InputStringConvert(self.prompt), input_control, ident_mode)
            else:
                self.coord_input.InitNextPointValueInput(AllplanIFW.InputStringConvert(self.prompt), input_control, ident_mode)

        if self.abscisssa_element is not None:
            self.coord_input.SetAbscissaElement(self.abscisssa_element, AllplanGeo.Matrix3D())


        geometry_snoop = AllplanIFW.SnoopElementGeometryFilter(
            bFindBaseGeometry        = True,
            bFindAreaGeometry        = False,
            bPerpendicularOnElement  = False,
            bFindNonPassiveOnly      = False,
            bSplitAreaGeometries     = False,
            bIdentifyEmbeddedElement = False,
            bFindCompleteFootprint   = False,
            splitElement3D           = AllplanIFW.eSplitElement3D.ELEMENT3D_EDGES,
        )
        self.coord_input.SetGeometryFilter(geometry_snoop)

    def start_end_point_input(self):
        """Start the input of the line's end point"""
        if self.coord_input is None:
            return

        ident_mode = AllplanIFW.CoordinateInputMode(AllplanIFW.eIdentificationMode.eIDENT_POINT)
        if self.default_input_value is None:
            self.coord_input.InitNextPointInput(AllplanIFW.InputStringConvert(self.prompt), ident_mode)
        else:
            input_control = AllplanIFW.ValueInputControlData(AllplanIFW.eValueInputControlType.eCOORDINATE_EDIT,
                                                            self.default_input_value,
                                                            True, False)
            self.coord_input.InitNextPointValueInput(AllplanIFW.InputStringConvert(self.prompt), input_control, ident_mode)


    def on_preview_draw(self):
        """ Handles the preview draw event
        """
        if self.coord_input is None:
            return

        if (input_line := self.get_input_line()) != AllplanGeo.Line3D():
            self.draw_preview(input_line)

        if self.default_input_value is not None:
            self.interactor_result.input_value = self.coord_input.GetInputControlValue()

    def on_mouse_leave(self):
        """ Handles the mouse leave event
        """

        self.on_preview_draw()


    def process_mouse_msg(self,
                          mouse_msg: int,
                          pnt      : AllplanGeo.Point2D,
                          msg_info : AllplanIFW.AddMsgInfo) -> bool:
        """ Handles the process mouse message event

        Args:
            mouse_msg: mouse message ID
            pnt:       input point in Allplan view coordinates
            msg_info:  additional mouse message info

        Returns:
            True/False for success.
        """
        if not self.coord_input:
            return True

        # the UVS adapter is got only during start point input
        # for the end point, the adapter from the start point input is used
        if self.start_point is None and self.allow_uvs_input:
            self.uvs_transform = self.UvsTransformation(self.coord_input.GetInputAssocView())

        # when the input line is a valid line, draw the preview or terminate interactor
        if (input_line := self.get_input_line(mouse_msg, pnt, msg_info)) != AllplanGeo.Line3D():
            # when mouse is clicked, save the input line and the element, to which it belongs,
            # in the results object and terminate the interactor
            if not self.coord_input.IsMouseMove(mouse_msg):
                self.interactor_result.input_line = input_line
                self.interactor_result.element    = self.coord_input.GetSelectedElement()
                if self.default_input_value is not None:
                    self.interactor_result.input_value = self.coord_input.GetInputControlValue()
                return False

            # when mouse is moved, only draw the preview
            self.draw_preview(input_line)
        return True

    @overload
    def get_input_line(self) -> AllplanGeo.Line3D:
        """Construct the input line from the mouse message. This overload is meant to be used inside
        events, where no mouse message is available ().


        Returns:
            The input line as follows:
            -   During start point input (no start_point is empty) resulting line is a zero-line.
            -   During end point input (start_point property is not empty) resulting line is
                constructed from the start_point and the current point
        """

    @overload
    def get_input_line(self,
                       mouse_msg: int,
                       pnt      : AllplanGeo.Point2D,
                       msg_info : AllplanIFW.AddMsgInfo) -> AllplanGeo.Line3D:
        """Construct the input line from the mouse message. This overload is meant to be used inside
        process_mouse_msg event.

        Args:
            mouse_msg: mouse message ID
            pnt:       input point in Allplan view coordinates
            msg_info:  additional mouse message info

        Returns:
            The input line as follows:
            -   During start point input (start_point property is empty):
                -   If line pick is allowed and a line was found, it will be returned.
                -   Otherwise
                    -   When mouse was clicked, the clicked point is saved in start_point property.
                    -   A zero-line is returned.
            -   During end point input (start_point property is not empty):
                -   resulting line is constructed from the start_point and the current point
        """

    def get_input_line(self,
                       mouse_msg: int = 512,
                       pnt      : AllplanGeo.Point2D = AllplanGeo.Point2D(),
                       msg_info : AllplanIFW.AddMsgInfo|None = None) -> AllplanGeo.Line3D:
        """Actual implementation

        Args:
            mouse_msg: mouse message ID
            pnt:       input point in Allplan view coordinates
            msg_info:  additional mouse message info

        Returns:
            Input line, if input was successful. Otherwise zero line.
        """
        if self.coord_input is None:
            return AllplanGeo.Line3D()

        # set the point to track to during end point input
        track_pnt = AllplanGeo.Point3D() if self.start_point is None else self.start_point * self.uvs_transform.world_to_uvs

        # perform point identification in the viewport
        if isinstance(msg_info, AllplanIFW.AddMsgInfo):
            input_result = self.coord_input.GetInputPoint(mouse_msg, pnt, msg_info,
                                                        track_pnt,
                                                        self.start_point is not None)
        else:
            input_result = self.coord_input.GetCurrentPoint(track_pnt,
                                                            self.start_point is not None)

        # perform line identification, if line picking is on
        # this is done only during the first point input
        if self.allow_pick_up and self.start_point is None:
            picked_line = None
            geo_element = self.coord_input.GetSelectedGeometryElement()
            match geo_element.__class__:
                case AllplanGeo.Line3D:
                    picked_line = cast(AllplanGeo.Line3D, geo_element)
                case AllplanGeo.Line2D:
                    picked_line = AllplanGeo.Line3D(geo_element)

            # if line was identified, return it
            if picked_line is not None:
                return AllplanGeo.Transform(picked_line, self.uvs_transform.uvs_to_world)

        # get the identified point in world coordinates
        input_point = input_result.GetPoint() * self.uvs_transform.uvs_to_world

        # during end point input, return a line from start to the end point
        if self.start_point is not None:
            return AllplanGeo.Line3D(self.start_point, input_point)

        # during start point input, when mouse was clicked, save the point as start point anr return zero-line
        if not self.coord_input.IsMouseMove(mouse_msg):
            self.start_point = input_point
            self.start_end_point_input()
        return AllplanGeo.Line3D()

    def draw_preview(self, line: AllplanGeo.Line3D) -> None:
        """Draw the preview during the input.

        If a function generating preview elements from a 3D line is defined, use it. Otherwise
        preview a red 3D line.

        Args:
            line:   line to preview
        """
        if isinstance(self.preview_function, Callable):
            preview_elements = self.preview_function(line)
        else:
            preview_elements = ModelEleList(AllplanBaseElements.CommonProperties())
            preview_elements.set_color(6)
            preview_elements.append_geometry_3d(line)

        if self.coord_input is not None:
            AllplanBaseElements.DrawElementPreview(self.coord_input.GetInputViewDocument(),
                                                   self.uvs_transform.world_to_uvs,
                                                   preview_elements,
                                                   True,
                                                   None)
    def on_cancel_function(self) -> BaseScriptObject.OnCancelFunctionResult:
        """Handles the event of hitting ESC during the input

        Cancels the input, when ESC is hit during the start point input. Otherwise restarts the start point input.

        Returns:
            False during the start point input, True otherwise
        """
        if self.start_point is None:
            return BaseScriptObject.OnCancelFunctionResult.CANCEL_INPUT
        self.start_point         = None
        self.uvs_transform       = self.UvsTransformation(AllplanEleAdapter.AssocViewElementAdapter())
        return BaseScriptObject.OnCancelFunctionResult.CONTINUE_INPUT

    class UvsTransformation():
        """Class representing transformation between UVS coordinate system and world coordinate system"""
        def __init__(self, uvs_adapter: AllplanEleAdapter.AssocViewElementAdapter):
            """Initialize from UVS

            Args:
                uvs_adapter:    element adapter pointing to the UVS
            """
            self.__world_to_uvs = AllplanGeo.Matrix3D() if uvs_adapter.IsNull() else uvs_adapter.GetTransformationMatrix()

        # pylint: disable=W9011
        @property
        def world_to_uvs(self) -> AllplanGeo.Matrix3D:
            """Transformation from world to UVS coordinate system"""
            return self.__world_to_uvs

        @property
        def uvs_to_world(self) -> AllplanGeo.Matrix3D:
            """Transformation from UVS to world coordinate system"""
            uvs_to_world = AllplanGeo.Matrix3D(self.__world_to_uvs)
            uvs_to_world.Reverse()
            return uvs_to_world
        # pylint: enable=W9011
