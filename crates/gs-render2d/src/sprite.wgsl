struct VsIn {
    @location(0) position: vec2<f32>,
    @location(1) uv: vec2<f32>,
    @location(2) color: vec4<f32>,
};

struct VsOut {
    @builtin(position) clip_position: vec4<f32>,
    @location(0) uv: vec2<f32>,
    @location(1) color: vec4<f32>,
};

@vertex
fn vs_main(v: VsIn) -> VsOut {
    var o: VsOut;
    o.clip_position = vec4<f32>(v.position, 0.0, 1.0);
    o.uv = v.uv;
    o.color = v.color;
    return o;
}

@group(0) @binding(0)
var t_atlas: texture_2d<f32>;
@group(0) @binding(1)
var s_atlas: sampler;

@fragment
fn fs_main(v: VsOut) -> @location(0) vec4<f32> {
    let texel = textureSample(t_atlas, s_atlas, v.uv);
    return texel * v.color;
}
