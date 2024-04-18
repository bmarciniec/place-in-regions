"""Module with distortion utility to manipulate the bending shapes for polygonal placements"""
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_Reinforcement as AllplanReinf


class BendingShapeDistortionUtil():
    """Utility for manipulating the bending shape"""
    def __init__(self,
                 top_vertices     : set[int],
                 distortion_vector: AllplanGeo.Vector3D = AllplanGeo.Vector3D(0,0,1)):
        """Initialize the utility

        Args:
            top_vertices:       indexes of the shape's top vertices, that should be distorted by the util
            distortion_vector:  vector defining the distortion direction
        """
        self.shape = AllplanReinf.BendingShape()
        self.top_vertices      = top_vertices
        self.distortion_vector = distortion_vector

    def get_distortion_dimension(self, shape: AllplanReinf.BendingShape) -> float:
        """Get the dimension of the bending shape measured along the distortion vector.

        E.g. if the distortion vector is (0,0,1), it is simply the height of the shape

        Args:
            shape: bending shape to get the dimension of

        Returns:
            distortion dimension
        """
        min_max = AllplanGeo.MinMax3D()
        rotation = AllplanGeo.Matrix3D()
        rotation.SetRotation(self.distortion_vector,
                             AllplanGeo.Vector3D(0,0,1))
        for point in shape.ShapePolyline.Points:
            AllplanGeo.AddToMinMax(min_max, point * rotation)
        return min_max.GetSizeZ()

    def distort_shape(self,
                      shape: AllplanReinf.BendingShape,
                      new_dimension: float) -> None:
        """Distort the given shape to adapt to a given dimension

        Only the top vertices of the shape polyline are moved for the shape to match the new dimension

        Args:
            shape:          shape to distort
            new_dimension:  aimed dimension of the shape after distortion

        Raises:
            ValueError: when the indices of the top vertices exceed the number of vertices in the shape
        """
        shape_polyline = shape.GetShapePolyline()
        if max(self.top_vertices) >= shape_polyline.Count():
            raise ValueError("Cannot distort the shape with this utility. Construct a new utility for distorting this shape")

        difference = new_dimension - self.get_distortion_dimension(shape)
        move_vec = AllplanGeo.Vector3D(self.distortion_vector)
        move_vec.Normalize(difference)

        for i in self.top_vertices:
            point = shape_polyline.GetPoint(i)
            shape_polyline.SetPoint(AllplanGeo.Move(point,move_vec),i)

        shape.SetShapePolyline(shape_polyline)
