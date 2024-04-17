import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_Reinforcement as AllplanReinf


class BendingShapeDistortionUtil():
    """Utility for manipulating the bending shape"""
    def __init__(self,
                 vertices_above   : set[int],
                 distortion_vector: AllplanGeo.Vector3D = AllplanGeo.Vector3D(0,0,1)):
        self.shape = AllplanReinf.BendingShape()
        self.vertices_above    = vertices_above
        self.distortion_vector = distortion_vector

    @property
    def distortion_dimension(self) -> float:
        """Dimension of the bending shape measured along the distortion vector

        E.g. if the distortion vector is (0,0,1), it is simply the height of the shape

        Changing the height will move the points of the polyline along the distortion vector
        """
        min_max = AllplanGeo.MinMax3D()
        rotation = AllplanGeo.Matrix3D()
        rotation.SetRotation(self.distortion_vector,
                             AllplanGeo.Vector3D(0,0,1))
        for point in self.shape.ShapePolyline.Points:
            AllplanGeo.AddToMinMax(min_max, point * rotation)
        return min_max.GetSizeZ()

    @distortion_dimension.setter
    def distortion_dimension(self, new_value: float):
        if self.shape == AllplanReinf.BendingShape():
            raise ValueError("Set a shape, before changing it with this utilitiy")
        difference = new_value - self.distortion_dimension
        move_vec = AllplanGeo.Vector3D(self.distortion_vector)
        move_vec.Normalize(difference)
        shape_polyline = self.shape.GetShapePolyline()
        for i in self.vertices_above:
            point = shape_polyline.GetPoint(i)
            shape_polyline.SetPoint(AllplanGeo.Move(point,move_vec),i)
        self.shape.SetShapePolyline(shape_polyline)
