# Copyright (c) 2013 Mak Nazecic-Andrlon
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import bpy
from bpy_extras.io_utils import ExportHelper
import struct
from array import array
import itertools

bl_info = {
    "name":         "Resequence ROBJ Format",
    "author":       "Mak Nazecic-Andrlon",
    "blender":      (2,6,7),
    "version":      (0,0,1),
    "location":     "File > Import-Export",
    "description":  "Export Resequence ROBJ models",
    "category":     "Import-Export"
}


class ExportROBJ(bpy.types.Operator, ExportHelper):
    bl_idname       = "export_robj.fmt"
    bl_label        = "Export ROBJ"
    bl_options      = {'PRESET'}

    filename_ext    = ".robj"

    def execute(self, context):
        scene = context.scene
        objects = []
        for ob in context.selected_objects:
            if not ob or ob.type != "MESH":
                raise NameError("Object %s is not a mesh" % ob)
            if not ob.data.uv_textures:
                raise RuntimeError("%s has no UV coords" % ob)
            objects.append(ob)

        # Process the UV coordinates and count the number of faces.
        num_faces = 0
        uv_data = array('f')
        for ob in objects:
            mesh = ob.to_mesh(scene, True, 'PREVIEW', calc_tessface=True)
            uv_faces = mesh.tessface_uv_textures.active.data
            if len(uv_faces) != len(mesh.tessfaces):
                raise RuntimeError("%s has unequal number of UV faces and mesh faces")
            for uv_face in uv_faces:
                uv = uv_face.uv
                if len(uv) == 3:
                    uv_data.extend(itertools.chain.from_iterable(uv))
                    num_faces += 1
                elif len(uv) == 4:
                    # Split a quad into two triangles if necessary. Blender
                    # uses clockwise winding for forward faces.
                    uv_data.extend(uv[0])
                    uv_data.extend(uv[1])
                    uv_data.extend(uv[2])

                    uv_data.extend(uv[0])
                    uv_data.extend(uv[2])
                    uv_data.extend(uv[3])
                    num_faces += 2
                else:
                    raise RuntimeError("Too many UV coords on %s" % ob)

        # Process the positions and normals of the vertices of every frame.
        vert_data = array('f')
        for frame_idx in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame_idx)
            # Buffers, to be recombined into vert_data at end of iteration.
            normal_data = array('f')
            position_data = array('f')
            for ob in objects:
                mesh = ob.to_mesh(scene, True, 'PREVIEW', calc_tessface=True)
                matrix_world = ob.matrix_world
                transformed = [matrix_world * v.co for v in mesh.vertices]

                for face in mesh.tessfaces:
                    # Split a quad into two triangles if necessary. Blender
                    # uses clockwise winding for forward faces.
                    if len(face.vertices) == 3:
                        face_vertices = tuple(face.vertices)
                    else:
                        face_vertices = (
                            face.vertices[0],
                            face.vertices[1],
                            face.vertices[2],

                            face.vertices[0],
                            face.vertices[2],
                            face.vertices[3]
                        )

                    # Process vertex normals.
                    if face.use_smooth:
                        # Use vertex normals if face smoothing is on (fancier).
                        for i in face_vertices:
                            normal_data.extend(matrix_world * mesh.vertices[i].normal)
                    else:
                        # Use face normals otherwise.
                        for i in face_vertices:
                            normal_data.extend(matrix_world * face.normal)

                    # Process vertex positions.
                    for i in face_vertices:
                        position_data.extend(transformed[i])
            vert_data += normal_data
            vert_data += position_data

        print("Processed %d meshes" % len(objects))
        print("Total %d UV coords and %d vertices" % (len(uv_data) / 3,
            len(vert_data) / 6))

        # Output everything.
        with open(self.filepath, "wb") as outfile:
            outfile.write(struct.pack("<3l", num_faces, scene.frame_start,
                scene.frame_end))
            uv_data.tofile(outfile)
            vert_data.tofile(outfile)
        print("Wrote %s" % self.filepath)

        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(ExportROBJ.bl_idname, text="Resequence ROBJ (.robj)")

def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_export.remove(menu_func)

if __name__ == "__main__":
    register()
