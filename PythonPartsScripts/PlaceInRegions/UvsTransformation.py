"""Module with the definition of OVS Transformation class"""
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter


class UvsTransformation():
    """Class representing transformation between UVS coordinate system and world coordinate system"""

    def __init__(self, uvs_adapter: AllplanEleAdapter.AssocViewElementAdapter = AllplanEleAdapter.AssocViewElementAdapter()):
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