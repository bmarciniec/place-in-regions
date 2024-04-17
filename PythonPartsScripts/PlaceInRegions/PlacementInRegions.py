"""Module with the implementation of the PlacementInRegion class"""
from __future__ import annotations

import re
from copy import copy
from dataclasses import dataclass
from typing import cast

import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_Reinforcement as AllplanReinf
from NemAll_Python_Utility import VecDoubleList
from StdReinfShapeBuilder import LinearBarPlacementBuilder as LinearBarBuilder

from .DistordableBendingShape import BendingShapeDistortionUtil
from .PolygonalPlacementInteractor import PolygonalPlacementInteractorResult
from .UvsTransformation import UvsTransformation


class PlacementInRegions():
    """Class representing the rebar placement in multiple regions with different spacing each.

    Examples:
        Instantiate the class first:

        >>> placement_in_regions = PlacementInRegions(bars_representation_line)

        Then call the place method to calculate the list of BarPlacements
        >>> placement_in_regions.place('5*100+10*125+$*250', placement_line)

        Get the calculated placements by reading the propery placements
        >>> placement_in_region.placements

    """
    def __init__(self,
                 bars_representation_line: AllplanEleAdapter.BaseElementAdapter,
                 start_cover             : float,
                 end_cover               : float,
                 uvs                     : AllplanEleAdapter.AssocViewElementAdapter = AllplanEleAdapter.AssocViewElementAdapter(),
                 )                       :
        """Initialize from a BaseElementAdapter of type BarsRepresentationLine_TypeUUID

        Args:
            bars_representation_line:   BaseElementAdapter of type BarsRepresentationLine_TypeUUID
            uvs:                        UVS in which the shape was selected

        Raises:
            ValueError: when the given BaseElementAdapter is not a BarsRepresentationLine_TypeUUID
        """
        if bars_representation_line.GetElementAdapterType().GetGuid() != AllplanEleAdapter.BarsRepresentationLine_TypeUUID:
            raise ValueError("A BarPlacement can only be constructed from a BarsRepresentationLine_TypeUUID, but a ",
                             bars_representation_line.GetElementAdapterType().GetTypeName(),
                             " was given.")

        self.start_cover = start_cover
        self.end_cover   = end_cover
        # set initial values
        self._bars_representation_line                    = bars_representation_line
        self._placements: list[AllplanReinf.BarPlacement] = []
        self._uvs_trans = UvsTransformation(uvs)

        # get bar definition from the bar representation line
        self._bars_definition = PlacementInRegions._get_bars_definition(bars_representation_line)

        # read the basic bar data, such as diameter, mark number, etc
        adapter_list = AllplanEleAdapter.BaseElementAdapterList([self._bars_definition])
        self.bar_data = cast(AllplanReinf.BarPositionData,
                             AllplanReinf.ReinforcementService.GetBarPositionData(adapter_list)[0])

    @property
    def placements(self) -> list[AllplanReinf.BarPlacement]:
        """The list of BarPlacement objects.

        Returns:
            List of BarPlacement objects

        Raises:
            RuntimeError: If the method place() was not call at least once.
        """
        if not self._placements:
            raise RuntimeError("No placements were calculated. Have you called the place() method?")
        return self._placements

    @property
    def bending_shape(self) -> AllplanReinf.BendingShape:
        """Definition of the bending shape to be placed

        The bending shape is created based on the data get from BaseElementAdapter (shape polyline, diameter, etc...)

        Returns:
            A bending shape object
        """
        # get the shape polygon
        shape_polygon_2d = cast(AllplanGeo.Polyline2D, self._bars_representation_line.GetGeometry())
        shape_polygon    = AllplanGeo.Polyline3D([AllplanGeo.Point3D(point) for point in shape_polygon_2d.Points])
        shape_polygon   *= self._uvs_trans.uvs_to_world

        _, shape_code, _ = AllplanReinf.ReinforcementService.GetBarShapeCode(self._bars_definition,
                                                                             AllplanReinf.ReinforcementService.eIso4066)

        shape_type = AllplanReinf.BendingShapeType.values[shape_code[0]]

        #TODO: when reading bending rollers from shape is possible, replace this with bending rollers from the shape
        bending_roller = AllplanReinf.BendingRollerService.GetBendingRollerFactor(self.bar_data.Diameter,
                                                                                  self.bar_data.SteelGrade,
                                                                                  concreteGrade = -1,
                                                                                  bStirrup      = True)

        return AllplanReinf.BendingShape(shapePol         = shape_polygon,
                                         bendingRoller    = VecDoubleList([bending_roller]*(shape_polygon.LineCount()-1) ),
                                         diameter         = self.bar_data.Diameter,
                                         steelGrade       = self.bar_data.SteelGrade,
                                         concreteGrade    = -1,
                                         bendingShapeType = shape_type)

    @staticmethod
    def _get_bars_definition(ele: AllplanEleAdapter.BaseElementAdapter) -> AllplanEleAdapter.BaseElementAdapter:
        """Inspect the parent elements of the given element adapter recursively up until
        an adapter of type BarsDefinition is found.

        Args:
            ele:    element adapter to inspect

        Returns:
            found parent element adapter of type BarsDefinition
        """
        parent_ele = AllplanEleAdapter.BaseElementAdapterParentElementService.GetParentElement(ele)

        if parent_ele.GetElementAdapterType() == AllplanEleAdapter.BarsDefinition_TypeUUID:
            return parent_ele
        return PlacementInRegions._get_bars_definition(parent_ele)

    def place(self,
              regions_string:    str,
              placement_line:    AllplanGeo.Line3D) -> None:
        """Place the rebars along a given 3D line in regions defined in a special string.

        Args:
            regions_string:     String describing placement regions. Each region is separated by a '+'
                                and consist of 'count * spacing[mm]', for example '5*100+10*125+$*250'.
                                At least one region must have an undefined count of spacing ('$')
            placement_line:     Line to place the rebars along
        """
        moved_shape = AllplanReinf.BendingShape(self.bending_shape)
        self._project_shape_on_point(moved_shape,
                                     placement_line.StartPoint)

        # get placement regions from the string
        placement_regions = self.placement_regions_from_string(regions_string,
                                                               self.bending_shape.GetDiameter())

        # calculate the list of pairs (start points, end point) for each placement region
        region_start_end_points = LinearBarBuilder.calculate_length_of_regions(
            placement_regions,
            placement_line.StartPoint,
            placement_line.EndPoint,
            concrete_cover_left  = 30,
            concrete_cover_right = 30) #TODO: remove hard-coded values

        self._placements.clear()

        # create one placement for each placement region
        for idx, start_end_point in enumerate(region_start_end_points):
            region_start_point, region_end_point = start_end_point

            self._placements.append(LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                self.bar_data.Position + idx,
                moved_shape,
                region_start_point,
                region_end_point,
                concrete_cover_left  = 0,    # start and end covers are already considered
                concrete_cover_right = 0,    # by calculate_length_of_regions
                bar_distance         = placement_regions[idx][1],
                global_move          = False))

            try:
                moved_shape.Move(AllplanGeo.Vector3D(region_start_end_points[idx + 1][0] - region_start_point))
            except IndexError:
                continue

    @staticmethod
    def _project_shape_on_point(shape:    AllplanReinf.BendingShape,
                                to_point: AllplanGeo.Point3D) -> None:
        """Move the shape onto a plane defined by a point.

        The movement is done by projecting the shape onto a plane parallel to the shape's plane,
        but located on a specified point.

        Args:
            shape:    shape, that will be moved
            to_point: point on the plane to move the shape onto
        """
        _, shape_plane = shape.ShapePolyline.IsPlanar()
        vec = AllplanGeo.Vector3D(to_point - shape_plane.Point)
        move_vector = shape_plane.Vector * vec.DotProduct(shape_plane.Vector)
        shape.Move(move_vector)


    @staticmethod
    def placement_regions_from_string(string: str, diameter: float) -> list[tuple[float,float,float]]:
        """Generate a list of tuples representing a placement region, out of a string

        Args:
            string:     String describing placement regions. Each region is separated by a '+'
                        and consist of 'count * spacing[mm]', for example '5*100+10*125+$*250'.
                        At least one region must have an undefined cound of spacing ('$')
            diameter:   Bar diameter

        Returns:
            list of tuples like (region length, spacing, bar diameter)

        Raises:
            ValueError: if the regions string does not match the regular the pattern
        """

        pattern = r"^(\d+|\$)\*?(\d+(\.\d+)?)(\+(\d+|\$)\*?(\d+(\.\d+)?))*$"
        if not(re.match(pattern, string) and string.count("$") == 1):
            raise ValueError("Regions string is invalid")
        strings = string.split("+")
        regions = []
        for region_string in strings:
            if "$" in region_string:
                region_string = region_string.replace("$", "1")
                region = (0.0, eval(region_string) ,diameter)
            elif "*" in region_string:
                region = (eval(region_string), float(region_string.split("*")[1]) ,diameter)
            else:
                region = (float(region_string),float(region_string), diameter )
            regions.append(region)

        return regions

class PolygonalPlacementInRegions(PlacementInRegions):
    """Class representing the polygonal rebar placement in multiple regions with different spacing each."""
    @dataclass
    class Region:
        """Class containing data relevant for an individual placement region"""
        bar_count : int
        start_pnt : AllplanGeo.Point2D
        height_at_start: float
        end_pnt : AllplanGeo.Point2D
        height_at_end: float

    def __init__(self,
                 bars_representation_line: AllplanEleAdapter.BaseElementAdapter,
                 cut_line                : AllplanGeo.Line2D,
                 start_cover             : float,
                 end_cover               : float,
                 uvs                     : AllplanEleAdapter.AssocViewElementAdapter = AllplanEleAdapter.AssocViewElementAdapter(),
                 ):

        """Initialize from a BaseElementAdapter of type BarsRepresentationLine_TypeUUID

        Args:
            bars_representation_line:   BaseElementAdapter of type BarsRepresentationLine_TypeUUID
            cut_line:                   Line cutting the shape in two parts
            uvs:                        UVS in which the shape was selected

        Raises:
            ValueError: when the given BaseElementAdapter is not a BarsRepresentationLine_TypeUUID
        """
        self.cut_line = cut_line
        super().__init__(bars_representation_line,start_cover,end_cover, uvs)

        # -------- construct the distortion utility
        shape_polygon_2d  = cast(AllplanGeo.Polyline2D, self._bars_representation_line.GetGeometry())
        def above(pnt: AllplanGeo.Point2D) -> bool:
            return AllplanGeo.Comparison.DeterminePosition(self.cut_line, pnt, 1e-11) == AllplanGeo.eComparisionResult.eAbove

        above_points = set(idx for idx, pnt in enumerate(shape_polygon_2d.Points) if above(pnt))

        self.distortion_util = BendingShapeDistortionUtil(above_points)

    def place(self,
              placement_data: PolygonalPlacementInteractorResult,
              spacing: float) -> None:
        """Foo"""
        start_shape = AllplanReinf.BendingShape(self.bending_shape)
        start_shape.Transform(placement_data.world_to_local)
        self._project_shape_on_point(start_shape, AllplanGeo.Point3D())

        self._placements.clear()
        placement_regions = self._populate_regions(placement_data,spacing)

        self.distortion_util.distortion_vector = AllplanGeo.Vector3D(0,1,0)

        # create one placement for each placement region
        for idx, region in enumerate(placement_regions):
            region_start_shape = AllplanReinf.BendingShape(start_shape)
            region_start_shape.Move(AllplanGeo.Vector2D(region.start_pnt).To3D)
            self.distortion_util.shape = region_start_shape
            self.distortion_util.distortion_dimension = region.height_at_start


            region_end_shape = AllplanReinf.BendingShape(start_shape)
            region_end_shape.Move(AllplanGeo.Vector2D(region.end_pnt).To3D)
            self.distortion_util.shape = region_end_shape
            self.distortion_util.distortion_dimension = region.height_at_end

            placement = AllplanReinf.BarPlacement(self.bar_data.Position + idx,
                                                  region.bar_count,
                                                  region_start_shape,
                                                  region_end_shape)

            placement.Transform(placement_data.local_to_world)
            self._placements.append(placement)

    def _populate_regions(self,
                          placement_data: PolygonalPlacementInteractorResult,
                          spacing: float) -> list[PolygonalPlacementInRegions.Region]:

        # define the placement line on the local X axis
        placement_line = AllplanGeo.Line2D(0,0,placement_data.total_length,0)
        placement_line.TrimStart(self.start_cover)
        placement_line.TrimEnd(self.end_cover)

        # divide the line into points one per each rebar
        placement_line_division = AllplanGeo.DivisionPoints(placement_line, float(spacing), 1e-11)
        division_points = [point.To2D for point in placement_line_division.GetPoints()]

        # fill the list with regions
        regions = []
        for polygon_3d in placement_data.elementary_polygons:
            lines = []
            _, polygon = AllplanGeo.ConvertTo2D(polygon_3d * placement_data.world_to_local)

            # find intersection points between Y axis and each polygon
            for point in division_points:
                axis = AllplanGeo.Axis2D(point, AllplanGeo.Vector2D(0,1))
                found, intersection_points = AllplanGeo.IntersectionCalculus(axis, polygon)
                if found and len(intersection_points) == 2:
                    lines.append(AllplanGeo.Line2D(intersection_points[0].To2D, intersection_points[1].To2D))

            bar_count = len(lines)

            if bar_count:
                region = self.Region(
                    bar_count      = bar_count,
                    start_pnt      = lines[0].StartPoint,
                    height_at_start= AllplanGeo.CalcLength(lines[0]),
                    end_pnt        = lines[-1].StartPoint,
                    height_at_end  = AllplanGeo.CalcLength(lines[-1]),
                )
                regions.append(region)
        return regions