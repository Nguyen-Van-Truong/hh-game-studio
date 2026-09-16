"""Trusted tiny negative fixtures inside the resource-capped export process."""
def run(bpy,profile,root):
    rows=[]
    def rejected(label,code):
        try:profile.preflight(bpy)
        except profile.ExportRejected as exc:passed=str(exc)==code
        else:passed=False
        rows.append({'label':label,'passed':passed})
        print('GT04_EXPORT_REJECT '+label+' '+str(passed),flush=True)
        if not passed:raise RuntimeError('native admission case failed: '+label)
    obj=bpy.data.objects[0]
    original_x=obj.location.x
    obj.driver_add('location',0).driver.expression=str(original_x)
    rejected('object_driver','EXPORT_DRIVER_UNSUPPORTED')
    obj.driver_remove('location',0);obj.animation_data_clear();obj.location.x=original_x
    bpy.context.scene.driver_add('gravity',0).driver.expression='0'
    rejected('scene_driver','EXPORT_DRIVER_UNSUPPORTED')
    bpy.context.scene.driver_remove('gravity',0);bpy.context.scene.animation_data_clear()
    material=bpy.data.materials.new('GT04_UNSUPPORTED_MATERIAL')
    rejected('material','EXPORT_DEPENDENCY_UNSUPPORTED');bpy.data.materials.remove(material)
    image=bpy.data.images.new('GT04_MISSING_IMAGE',1,1)
    image.source='FILE';image.filepath=str(root/'does-not-exist.png')
    rejected('missing_texture','EXPORT_MISSING_TEXTURE');bpy.data.images.remove(image)
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
    rejected('linked_library','EXPORT_LINKED_LIBRARY_UNSUPPORTED')
    path.unlink()
    rejected('missing_library','EXPORT_MISSING_LIBRARY')
    for linked in list(bpy.data.objects):
        if linked.library:bpy.data.objects.remove(linked,do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.library:bpy.data.meshes.remove(mesh)
    for library in list(bpy.data.libraries):bpy.data.libraries.remove(library)
    bpy.context.view_layer.update()
    profile.preflight(bpy)
    return rows
