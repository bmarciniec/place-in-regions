"""Module with the implementation of the PlacementInRegion class"""
import re
from typing import cast

import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_Reinforcement as AllplanReinf
from NemAll_Python_Utility import VecDoubleList
from StdReinfShapeBuilder import LinearBarPlacementBuilder as LinearBarBuilder


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
                 uvs:                      AllplanEleAdapter.AssocViewElementAdapter = AllplanEleAdapter.AssocViewElementAdapter()):
        """Initialize from a BaseElementAdapter of type BarsRepresentationLine_TypeUUID

        Args:
            bars_representation_line:  BaseElementAdapter of type BarsRepresentationLine_TypeUUID

        Raises:
            ValueError: when the given BaseElementAdapter is not a BarsRepresentationLine_TypeUUID
        """
        if bars_representation_line.GetElementAdapterType().GetGuid() != AllplanEleAdapter.BarsRepresentationLine_TypeUUID:
            raise ValueError("A BarPlacement can only be constructed from a BarsRepresentationLine_TypeUUID, but a ",
                             bars_representation_line.GetElementAdapterType().GetTypeName(),
                             " was given.")

        # set initial values
        self.__bars_representation_line                    = bars_representation_line
        self.__placements: list[AllplanReinf.BarPlacement] = []
        self.__uvs = uvs
        # get bar definition from the bar representation line
        self.__bars_definition = PlacementInRegions.__get_bars_definition(bars_representation_line)

        # read the basic bar data, such as diameter, mark number, etc
        adapter_list = AllplanEleAdapter.BaseElementAdapterList([self.__bars_definition])
        self.bar_data = cast(AllplanReinf.BarPositionData,
                             AllplanReinf.ReinforcementService.GetBarPositionData(adapter_list)[0])

        # create the bending shape
        self.bending_shape = self.__create_bending_shape()

    @property
    def placements(self) -> list[AllplanReinf.BarPlacement]:
        """The list of BarPlacement objects.

        Returns:
            List of BarPlacement objects

        Raises:
            RuntimeError: If the method place() was not call at least once.
        """
        if not self.__placements:
            raise RuntimeError("No placements were calculated. Have you called the place() method?")
        return self.__placements

    def __create_bending_shape(self) -> AllplanReinf.BendingShape:
        """Construct a BendingShape object based on the bar definition inside a BaseElementAdapter

        Returns:
            A bending shape object
        """
        # get the shape polygon
        # shape_polygon     = cast(AllplanGeo.Polyline3D, self.__bars_definition.GetGeometry())
        shape_polygon_2d = cast(AllplanGeo.Polyline2D, self.__bars_representation_line.GetGeometry())
        shape_polygon  = AllplanGeo.Polyline3D([AllplanGeo.Point3D(point) for point in shape_polygon_2d.Points])
        view_to_world = self.__uvs.GetTransformationMatrix()
        view_to_world.Reverse()
        shape_polygon *= view_to_world

        _, shape_code, _ = AllplanReinf.ReinforcementService.GetBarShapeCode(self.__bars_definition,
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
    def __get_bars_definition(ele: AllplanEleAdapter.BaseElementAdapter) -> AllplanEleAdapter.BaseElementAdapter:
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
        return PlacementInRegions.__get_bars_definition(parent_ele)

    def place(self,
              regions_string:    str,
              placement_line:    AllplanGeo.Line3D) -> None:
        """Place the rebars along a given 3D line in regions defined in a special string.

        Args:
            regions_string:     String describing placement regions. Each region is separated by a '+'
                                and consist of 'count * spacing[mm]', for example '5*100+10*125+$*250'.
                                At least one region must have an undefined cound of spacing ('$')
            placement_line:     Line to place the rebars along
        """
        # move shape to start point
        moved_shape = AllplanReinf.BendingShape(self.bending_shape)
        _, shape_plane = moved_shape.ShapePolyline.IsPlanar()
        vec = AllplanGeo.Vector3D(placement_line.StartPoint - shape_plane.Point)
        move_vector = shape_plane.Vector * vec.DotProduct(shape_plane.Vector)
        moved_shape.Move(move_vector)

        # get placement region sfrom the string
        placement_regions = self.__placement_regions_from_string(regions_string,
                                                                 self.bending_shape.GetDiameter())

        # calculate the list of pairs (start points, end point) for each placement region
        region_start_end_points = LinearBarBuilder.calculate_length_of_regions(
            placement_regions,
            placement_line.StartPoint,
            placement_line.EndPoint,
            concrete_cover_left  = 30,
            concrete_cover_right = 30) #TODO: remove hard-coded values

        self.__placements.clear()

        # create one placement for each placement region
        for idx, start_end_point in enumerate(region_start_end_points):
            region_start_point, region_end_point = start_end_point

            self.__placements.append(LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
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
    def __placement_regions_from_string(string: str, diameter: float) -> list[tuple[float,float,float]]:
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
