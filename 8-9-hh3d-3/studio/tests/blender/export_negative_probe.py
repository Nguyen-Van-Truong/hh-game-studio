"""Trusted tiny negative fixtures inside the resource-capped export process."""
def run(bpy,profile,root):
    from unittest.mock import patch
    rows=[]
    def rejected(label,code):
        try:profile.preflight(bpy)
        except profile.ExportRejected as exc:passed=str(exc)==code
        else:passed=False
        rows.append({'label':label,'passed':passed})
        print('GT04_EXPORT_REJECT '+label+' '+str(passed),flush=True)
        if not passed:raise RuntimeError('native admission case failed: '+label)
    def rejected_without_io(label,code):
        with patch.object(profile,'Path',side_effect=AssertionError('unsupported dependency filesystem access')), \
             patch.object(bpy.path,'abspath',side_effect=AssertionError('unsupported dependency resolution')):
            rejected(label,code)
        rows[-1]['filesystem_access_blocked']=True
    obj=bpy.data.objects[0]
    original_x=obj.location.x
    obj.driver_add('location',0).driver.expression=str(original_x)
    rejected('object_driver','EXPORT_DRIVER_UNSUPPORTED')
    obj.driver_remove('location',0);obj.animation_data_clear();obj.location.x=original_x
    bpy.context.scene.driver_add('gravity',0).driver.expression='0'
    rejected('scene_driver','EXPORT_DRIVER_UNSUPPORTED')
    bpy.context.scene.driver_remove('gravity',0);bpy.context.scene.animation_data_clear()
    material=bpy.data.materials.new('GT04_UNSUPPORTED_MATERIAL')
    rejected('material','EXPORT_MATERIAL_STABLE_ID');bpy.data.materials.remove(material)
    image=bpy.data.images.new('GT04_MISSING_IMAGE',1,1)
    image.source='FILE';image.filepath=str(root/'does-not-exist.png')
    rejected_without_io('missing_texture','EXPORT_IMAGE_UNSUPPORTED');bpy.data.images.remove(image)
    group=bpy.data.node_groups.new('GT04_UNSUPPORTED_GN','GeometryNodeTree')
    rejected('geometry_nodes','EXPORT_DEPENDENCY_UNSUPPORTED');bpy.data.node_groups.remove(group)
    addons=bpy.context.preferences.addons
    unsupported=addons.new();unsupported.module='hh_unapproved_fixture'
    rejected('unapproved_addon','EXPORT_ADDON_SET');addons.remove(unsupported)
    addons.remove(addons['io_scene_gltf2'])
    rejected('missing_exporter_addon','EXPORT_ADDON_SET');addons.new().module='io_scene_gltf2'
    path=root/'owned-library.blend'
    bpy.data.libraries.write(str(path),{obj},fake_user=True)
    with bpy.data.libraries.load(str(path),link=True) as (source,target):target.objects=[source.objects[0]]
    rejected_without_io('linked_library','EXPORT_LINKED_LIBRARY_UNSUPPORTED')
    path.unlink()
    rejected_without_io('missing_library','EXPORT_LINKED_LIBRARY_UNSUPPORTED')
    for linked in list(bpy.data.objects):
        if linked.library:bpy.data.objects.remove(linked,do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.library:bpy.data.meshes.remove(mesh)
    for material in list(bpy.data.materials):
        if material.library:bpy.data.materials.remove(material)
    for library in list(bpy.data.libraries):bpy.data.libraries.remove(library)
    if obj.data.materials:
        material=obj.data.materials[0]
        shader=next(node for node in material.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
        shader.inputs['Transmission Weight'].default_value=.5
        rejected('material_transmission','EXPORT_MATERIAL_UNSUPPORTED_INPUT')
        shader.inputs['Transmission Weight'].default_value=0
        shader.inputs['Alpha'].default_value=.5
        rejected('material_alpha','EXPORT_MATERIAL_UNSUPPORTED_INPUT');shader.inputs['Alpha'].default_value=1
        extra=material.node_tree.nodes.new('ShaderNodeTexNoise')
        rejected('material_procedural_node','EXPORT_MATERIAL_NODE_GRAMMAR');material.node_tree.nodes.remove(extra)
        material.node_tree.driver_add('nodes["Principled BSDF"].inputs["Metallic"].default_value').driver.expression='0'
        rejected('material_node_driver','EXPORT_MATERIAL_NODE_GRAMMAR')
        material.node_tree.driver_remove('nodes["Principled BSDF"].inputs["Metallic"].default_value')
        material.node_tree.animation_data_clear()
        obj.data.materials.append(material)
        rejected('material_extra_slot','EXPORT_MATERIAL_SLOT_GRAMMAR');obj.data.materials.pop(index=1)
    bpy.context.view_layer.update()
    profile.preflight(bpy)
    return rows
