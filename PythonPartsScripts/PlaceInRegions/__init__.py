""" Module with the implementation of an Allplan extension PlaceInRegions for
placing bending shapes along a line in regions with variable spacings"""
from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import TYPE_CHECKING

import NemAll_Python_BaseElements as AllplanBaseElements
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_IFW_Input as AllplanIFW
import NemAll_Python_Reinforcement as AllplanReinf
from BaseScriptObject import BaseScriptObject
from CreateElementResult import CreateElementResult
from ScriptObjectInteractors.ScriptObjectInteractorResult import ScriptObjectInteractorResult
from ScriptObjectInteractors.SingleElementSelectInteractor import SingleElementInteractor
from Utils import LibraryBitmapPreview

from .LineScriptObjectInteractor import LineInteractor, LineInteractorResult
from .PlacementInRegions import PlacementInRegions

if TYPE_CHECKING:
    from __BuildingElementStubFiles.GetBendingShapeBuildingElement import GetBendingShapeBuildingElement as BuildingElement  # type: ignore
else:
    from BuildingElement import BuildingElement


def check_allplan_version(_build_ele: BuildingElement,
                          version  : str) -> bool:
    """ Check the current Allplan version

    Args:
        _build_ele: building element with the parameter properties
        version:    the current Allplan version

    Returns:
        True if version equal or newer than 2024
    """

    return float(version) >= 2024.0


def create_preview(build_ele : BuildingElement,
                   _doc      : AllplanEleAdapter.DocumentAdapter) -> CreateElementResult:
    """ Creation of the element preview

    Args:
        build_ele:  building element with the parameter properties
        _doc:       document of the Allplan drawing files

    Returns:
        created elements for the preview
    """

    script_path = Path(build_ele.pyp_file_path) / Path(build_ele.pyp_file_name).name
    thumbnail_path = script_path.with_suffix(".png")

    return CreateElementResult(LibraryBitmapPreview.create_library_bitmap_preview(str(thumbnail_path)))


def create_script_object(build_ele  : BuildingElement,
                         coord_input: AllplanIFW.CoordinateInput) -> BaseScriptObject:
    """ Creation of the script object

    Args:
        build_ele:   building element with the parameter properties
        coord_input: API object for the coordinate input, element selection, ... in the Allplan view

    Returns:
        created script object
    """

    return PlaceInRegions(build_ele, coord_input)


class PlaceInRegions(BaseScriptObject):
    """Implementation of an PythonPart for placing a selected rebar bending shape
    along a line in regions with variable spacing
    """
    class InputMode(IntEnum):
        """Definitions of possible input modes"""
        SHAPE_SELECTION = 1
        """Input mode, when the user has to select a bending shape"""
        LINE_INPUT = 2
        """Input mode, when the user must define the placement line"""
        CREATION = 3
        """Input mode, when the user creates the placement and can modify parameters in the palette"""

    def __init__(self,
                 build_ele: BuildingElement,
                 coord_input: AllplanIFW.CoordinateInput):
        """Default constructor

        Args:
            build_ele:      building element with parameter values from the property palette
            coord_input:    object representing the coordinate input inside the viewport
        """
        super().__init__(coord_input)

        # set inital values
        self.build_ele                   = build_ele
        self.shape_selection_result      = ScriptObjectInteractorResult()
        self.placement_line_input_result = LineInteractorResult()
        self.placement_in_regions        = None
        self.current_mode                = 0

    @property
    def current_mode(self) -> PlaceInRegions.InputMode:
        """Current input mode"""
        return self.__mode

    @current_mode.setter
    def current_mode(self, new_mode: PlaceInRegions.InputMode) -> None:
        self.script_object_interactor = None    # always terminate the old interactor

        # actions on switch into shape selection
        if new_mode == self.InputMode.SHAPE_SELECTION:
            self.shape_selection_result   = ScriptObjectInteractorResult()
            self.placement_in_regions     = None
            self.script_object_interactor = SingleElementInteractor(self.shape_selection_result,
                                                                    [AllplanEleAdapter.BarsRepresentationLine_TypeUUID])
            print("switched to shape selection")

        # actions on switch into line input
        elif new_mode == self.InputMode.LINE_INPUT:
            self.placement_line_input_result = LineInteractorResult()
            self.script_object_interactor = LineInteractor(self.placement_line_input_result,
                                                           is_first_input     = False,
                                                           prompt             = "Input placement line",
                                                           allow_pick_up      = True,
                                                           allow_input_in_uvs = True,
                                                           preview_function   = self.generate_preview_placements)
            print("switched to line input")

        # actions on switch into creation mode
        elif new_mode == self.InputMode.CREATION:
            print("switched to creation")

        self.__mode = new_mode

    def execute(self) -> CreateElementResult:
        """Execute the element creation

        Returns:
            created element
        """
        if isinstance(self.placement_in_regions, PlacementInRegions) and \
            self.placement_line_input_result != LineInteractorResult():

            self.placement_in_regions.place(self.build_ele.RegionsString.value,
                                            self.placement_line_input_result.input_line)
            placements = self.placement_in_regions.placements

            return CreateElementResult(elements         = placements,
                                       placement_point  = AllplanGeo.Point3D())
        return CreateElementResult()

    def start_input(self):
        """Start the element selection"""
        self.current_mode = self.InputMode.SHAPE_SELECTION

    def start_next_input(self):
        if self.current_mode == self.InputMode.LINE_INPUT:
            self.current_mode = self.InputMode.CREATION
            return

        if self.current_mode == self.InputMode.SHAPE_SELECTION:
            if self.placement_in_regions is None:
                bar_line                  = self.shape_selection_result.sel_element
                assoc_view                = self.coord_input.GetInputAssocView()
                self.placement_in_regions = PlacementInRegions(bar_line, assoc_view)

            if not isinstance(self.script_object_interactor, LineInteractor):
                self.current_mode = self.InputMode.LINE_INPUT
            return

        self.start_input()

    def generate_preview_placements(self, line: AllplanGeo.Line3D) -> list[AllplanReinf.BarPlacement]:
        """Generate the BarPlacements for preview

        Args:
            line:  placement line

        Returns:
            list of placements for preview generation
        """
        if isinstance(self.placement_in_regions, PlacementInRegions):
            self.placement_in_regions.place(self.build_ele.RegionsString.value, line)
            return self.placement_in_regions.placements
        return []

    def on_cancel_function(self) -> BaseScriptObject.OnCancelFunctionResult:
        """ Handles the cancel function event.

        This event is triggered by hitting ESC during the runtime of a PythonPart.
        In this case, the selection is terminated as well as the PythonPart itself

        Returns:
            Always cancel the input and terminate PythonPart
        """
        if self.current_mode == self.InputMode.SHAPE_SELECTION:
            self.script_object_interactor = None
            return self.OnCancelFunctionResult.CANCEL_INPUT

        if self.current_mode == self.InputMode.LINE_INPUT:
            if (cancel_result := self.script_object_interactor.on_cancel_function()) == self.OnCancelFunctionResult.CANCEL_INPUT:
                self.current_mode = self.InputMode.SHAPE_SELECTION
                self.script_object_interactor.start_input(self.coord_input)
                return self.OnCancelFunctionResult.CONTINUE_INPUT
            return cancel_result

        AllplanBaseElements.DeleteElements(self.document,
                                           AllplanEleAdapter.BaseElementAdapterList([self.shape_selection_result.sel_element]))

        return self.OnCancelFunctionResult.CREATE_ELEMENTS
