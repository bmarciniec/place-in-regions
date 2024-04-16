import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_Reinforcement as AllplanReinf
from NemAll_Python_Utility import VecDoubleList


class DistordableBendingShape(AllplanReinf.BendingShape):
    def __init__(self,
                 shape_polygon    : AllplanGeo.Polyline3D,
                 vertices_above   : set[int],
                 vertices_below   : set[int],
                 bending_roller   : VecDoubleList,
                 diameter         : float,
                 steel_grade      : int,
                 concrete_grade   : int,
                 shape_type       : AllplanReinf.BendingShapeType,
                 distortion_vector: AllplanGeo.Vector3D = AllplanGeo.Vector3D(0,0,1))                            :

        self.vertices_above    = vertices_above
        self.vertices_below    = vertices_below
        self.distortion_vector = distortion_vector
        super().__init__(shapePol         = shape_polygon,
                         bendingRoller    = bending_roller,
                         diameter         = diameter,
                         steelGrade       = steel_grade,
                         concreteGrade    = concrete_grade,
                         bendingShapeType = shape_type)

