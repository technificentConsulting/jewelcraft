# ##### BEGIN GPL LICENSE BLOCK #####
#
#  JewelCraft jewelry design toolkit for Blender.
#  Copyright (C) 2015-2020  Mikhail Rachinskiy
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####


import bpy
from bpy.props import EnumProperty, FloatProperty, BoolProperty
from bpy.types import Operator

from .. import var
from ..lib import asset, dynamic_list, unit


def upd_set_weight(self, context):
    if self.stone == "DIAMOND" and self.cut == "ROUND":
        self["weight"] = unit.convert_mm_ct(unit.Scale(context).from_scene(self.size))


def upd_weight(self, context):
    self["size"] = unit.Scale(context).to_scene(unit.convert_ct_mm(self.weight))


class OBJECT_OT_gem_add(Operator):
    bl_label = "Add Gem"
    bl_description = "Add gemstone to the scene"
    bl_idname = "object.jewelcraft_gem_add"
    bl_options = {"REGISTER", "UNDO"}

    cut: EnumProperty(name="Cut", items=dynamic_list.cuts, update=upd_set_weight)
    stone: EnumProperty(name="Stone", items=dynamic_list.stones, update=upd_set_weight)
    size: FloatProperty(
        name="Size",
        default=1.0,
        min=0.0001,
        step=5,
        precision=2,
        unit="LENGTH",
        update=upd_set_weight,
    )
    weight: FloatProperty(
        name="Carats",
        description="Round diamonds only",
        default=0.004,
        min=0.0001,
        step=0.1,
        precision=3,
        update=upd_weight,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(self, "size")
        col = layout.column()
        col.enabled = self.stone == "DIAMOND" and self.cut == "ROUND"
        col.prop(self, "weight")
        layout.prop(self, "stone")
        split = layout.split(factor=0.385)
        split.row()
        split.template_icon_view(self, "cut", show_labels=True)

    def execute(self, context):
        scene = context.scene
        view_layer = context.view_layer
        space_data = context.space_data
        cut_name = var.CUTS[self.cut].name
        stone_name = var.STONES[self.stone].name
        color = var.STONES[self.stone].color or self.color

        for ob in context.selected_objects:
            ob.select_set(False)

        imported = asset.asset_import(var.GEM_ASSET_FILEPATH, ob_name=cut_name)
        ob = imported.objects[0]
        context.collection.objects.link(ob)

        if space_data.local_view:
            ob.local_view_set(space_data, True)

        ob.scale *= self.size
        ob.location = scene.cursor.location
        ob.select_set(True)
        ob["gem"] = {"cut": self.cut, "stone": self.stone}

        asset.add_material(ob, name=stone_name, color=color, is_gem=True)

        if context.mode == "EDIT_MESH":
            asset.ob_copy_to_faces(ob)
            bpy.ops.object.mode_set(mode="OBJECT")

        view_layer.objects.active = ob

        return {"FINISHED"}

    def invoke(self, context, event):
        self.color = asset.color_rnd()

        wm = context.window_manager
        return wm.invoke_props_dialog(self)


class OBJECT_OT_gem_edit(Operator):
    bl_label = "Edit Gem"
    bl_description = "Edit selected gems"
    bl_idname = "object.jewelcraft_gem_edit"
    bl_options = {"REGISTER", "UNDO"}

    cut: EnumProperty(name="Cut", items=dynamic_list.cuts, options={"SKIP_SAVE"})
    stone: EnumProperty(name="Stone", items=dynamic_list.stones, options={"SKIP_SAVE"})
    use_id_only: BoolProperty(
        name="Only ID",
        description="Only edit gem identifiers, not affecting object data and materials",
        options={"SKIP_SAVE"},
    )
    use_force: BoolProperty(
        name="Force Edit",
        description="Force edit selected mesh objects, can be used to make gems from non-gem objects",
        options={"SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(self, "stone")
        split = layout.split(factor=0.385)
        split.row()
        split.template_icon_view(self, "cut", show_labels=True)

        layout.separator()

        layout.prop(self, "use_id_only")
        layout.prop(self, "use_force")

    def execute(self, context):
        obs = context.selected_objects
        cut_name = var.CUTS[self.cut].name
        stone_name = var.STONES[self.stone].name
        color = var.STONES[self.stone].color or self.color

        imported = asset.asset_import(var.GEM_ASSET_FILEPATH, me_name=cut_name)
        me = imported.meshes[0]

        for ob in obs:

            if ob.type != "MESH":
                continue

            if self.use_force or "gem" in ob:

                if self.use_force:
                    ob["gem"] = {}

                if self.use_force or ob["gem"]["cut"] != self.cut:

                    ob["gem"]["cut"] = self.cut

                    if not self.use_id_only:
                        size_orig = ob.dimensions[1]
                        mats_orig = ob.data.materials

                        ob.data = me.copy()
                        ob.name = cut_name

                        ob.scale = (size_orig, size_orig, size_orig)
                        asset.apply_scale(ob)

                        for mat in mats_orig:
                            ob.data.materials.append(mat)

                if self.use_force or ob["gem"]["stone"] != self.stone:

                    ob["gem"]["stone"] = self.stone

                    if not self.use_id_only:

                        if ob.data.users > 1:
                            ob.data = ob.data.copy()

                        asset.add_material(ob, name=stone_name, color=color, is_gem=True)

        bpy.data.meshes.remove(me)

        return {"FINISHED"}

    def invoke(self, context, event):
        if not context.selected_objects:
            self.report({"ERROR"}, "At least one gem object must be selected")
            return {"CANCELLED"}

        ob = context.object

        if ob is not None and "gem" in ob:
            self.cut = ob["gem"]["cut"]
            self.stone = ob["gem"]["stone"]

        self.color = asset.color_rnd()

        wm = context.window_manager
        return wm.invoke_props_popup(self, event)


class OBJECT_OT_gem_id_convert_deprecated(Operator):
    bl_label = "Convert Deprecated Gem IDs"
    bl_description = "Convert deprecated gem identifiers to compatible for all objects in the scene"
    bl_idname = "object.jewelcraft_gem_id_convert_deprecated"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obs = context.scene.objects

        for ob in obs:
            if ob.type == "MESH" and "gem" in ob.data:

                if "gem" not in ob:
                    ob["gem"] = {}

                    for k, v in ob.data["gem"].items():
                        if k.lower() == "cut":
                            ob["gem"]["cut"] = v
                        elif k.lower() == "type":
                            ob["gem"]["stone"] = v

                del ob.data["gem"]

                if ob.data.users > 1:
                    for link in obs:
                        if link.data is ob.data:
                            link["gem"] = ob["gem"]

        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_confirm(self, event)
