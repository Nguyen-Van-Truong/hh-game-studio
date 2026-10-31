"""HH Studio self-authored flat cel heads. Run only inside pinned Blender.

blender.exe --background --factory-startup --disable-autoexec --offline-mode \
  --python tools/build_chibi_blender_heads.py

The authored medium is Blender layered polygon meshes, not raster painting or
reference extraction. Each named character/expression mesh remains editable in .blend.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import time

import bpy
from mathutils import Vector
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/sprites/chibi_brawler/r5_heads"
ART = ROOT / "art/chibi_r5"
CELL = 128
EXPRESSIONS = ["CHEEKY_SMIRK", "BLAZING_GLARE", "WIDE_MOUTH_SHOUT",
               "DIZZY_SPIRAL_HURT", "ECSTATIC_VICTORY_LAUGH", "LOW_HP_SWEAT", "KO_STARS", "BLINK"]
ROSTER = ["johnny", "boris", "agent", "hideki", "blaire", "savage", "cruger", "ivan",
          "brody", "mac", "billy", "scott", "funnyman", "jeff", "solaria", "atlas",
          "shinobi", "tideweaver", "goku", "luffy", "naruto", "saitama"]
EXTRA_ROWS = ["goku_awakened", "naruto_awakened"]
ALL_ROWS = ROSTER + EXTRA_ROWS
INK = "#171B28"
WHITE = "#FFF7E8"
STYLES = {
    "johnny": ("spikes", "#3D2A2A", "#735047", "#FF7832", "#F8C78E", "#B9684C", "#84452D"),
    "boris": ("crop", "#484752", "#74717A", "#A9A5AB", "#DCA87F", "#975F50", "#5C697F"),
    "agent": ("slick", "#202B3A", "#435164", "#7395A5", "#E1B38C", "#9E6C56", "#619DB4"),
    "hideki": ("tied", "#222633", "#414656", "#D43A49", "#F0BE96", "#B4775F", "#703338"),
    "blaire": ("bob", "#48324F", "#865A87", "#CD84B5", "#F5C7AB", "#B67B76", "#61A697"),
    "savage": ("mohawk", "#6B3032", "#C25B48", "#F8B45A", "#B8815D", "#774B43", "#B0A06C"),
    "cruger": ("cap", "#4D4934", "#807756", "#C1B47A", "#C99168", "#885B49", "#8B9568"),
    "ivan": ("beard", "#693E2A", "#AE6841", "#E6A35F", "#E8B58A", "#A66D53", "#74A9BF"),
    "brody": ("visor", "#242A32", "#4C5666", "#62D3E4", "#A16D50", "#69463B", "#E0B868"),
    "mac": ("quiff", "#9E7137", "#D5AD5D", "#FFDE91", "#EDBB8C", "#A56F54", "#5B9A91"),
    "billy": ("bandana", "#55372B", "#8E5B3C", "#D85347", "#E5AD7D", "#9B624F", "#927750"),
    "scott": ("patrol", "#263848", "#455B72", "#E9BD63", "#DFAC84", "#9B6957", "#779BBB"),
    "funnyman": ("clown", "#2D6F5E", "#56AD7B", "#CF4F5C", "#F6E1C5", "#C5A08D", "#5A9477"),
    "jeff": ("baldbeard", "#3F302D", "#6E5145", "#BC8960", "#B57D56", "#795241", "#CC9A57"),
    "solaria": ("sun", "#B94F30", "#F18C3D", "#FFD06B", "#F2BD88", "#BD7656", "#F4C967"),
    "atlas": ("tech", "#253B47", "#496476", "#77E8CB", "#BC8C6C", "#805D4E", "#7AE6BF"),
    "shinobi": ("ninja", "#A0B0C3", "#CED9E2", "#F7F4DF", "#E6B88F", "#9D6C60", "#9D68D5"),
    "tideweaver": ("wave", "#1F5C70", "#3294A4", "#8CE6D7", "#C5B6A2", "#8C7C79", "#61D9C9"),
    "goku": ("dragon", "#20242E", "#414653", "#75818F", "#F5BC81", "#AB714F", "#655647"),
    "luffy": ("straw", "#29262C", "#51414A", "#D7443D", "#EFB585", "#AC7153", "#5C4337"),
    "naruto": ("fox", "#D3972E", "#F4C54B", "#FFE88C", "#F1BA88", "#A97257", "#53A4C2"),
    "saitama": ("bald", "#C49368", "#EABD87", "#FFE3A2", "#E8B482", "#A97554", "#664E3E"),
    "goku_awakened": ("dragon", "#D79D31", "#F5CB5A", "#FFF2A1", "#F5BC81", "#AB714F", "#54C8B5"),
    "naruto_awakened": ("fox", "#D89024", "#FFD05A", "#FFF6A1", "#FFCF83", "#C38B45", "#CF5736"),
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def catmull(points, closed=True, steps=5):
    result = []
    n = len(points)
    for i in range(n if closed else n - 1):
        p0 = points[(i - 1) % n] if closed or i else points[0]
        p1, p2 = points[i], points[(i + 1) % n]
        p3 = points[(i + 2) % n] if closed or i + 2 < n else points[-1]
        for j in range(steps):
            t = j / steps
            result.append(tuple(.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
                                (2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t*t +
                                (-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t*t*t) for k in (0, 1)))
    if not closed:
        result.append(points[-1])
    return result


MATERIALS = {}


def material(hex_color):
    if hex_color not in MATERIALS:
        c = [int(hex_color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        c = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055)**2.4 for v in c]
        m = bpy.data.materials.new("Cel " + hex_color)
        m.diffuse_color = (*c, 1)
        m.use_nodes = True
        nodes = m.node_tree.nodes
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs[0].default_value = (*c, 1)
        emission.inputs[1].default_value = 1
        m.node_tree.links.new(emission.outputs[0], output.inputs[0])
        MATERIALS[hex_color] = m
    return MATERIALS[hex_color]


class Drawing:
    def __init__(self, name, col, row):
        self.name, self.ox, self.oy = name, col * CELL, row * CELL
        self.vertices, self.faces, self.colors, self.palette = [], [], [], []
        self.layer = 0

    def poly(self, points, color, stroke=None, width=2.1, smooth=False):
        points = catmull(points) if smooth else points
        self.layer += 1
        # Four transparent pixels around each cell protect filtered atlas edges.
        vectors = [Vector((max(5, min(123, float(x))), max(5, min(123, float(y))), 0)) for x, y in points]
        triangles = tessellate_polygon([vectors])
        if color not in self.palette:
            self.palette.append(color)
        index = self.palette.index(color)
        for tri in triangles:
            start = len(self.vertices)
            coords = [vectors[v] if isinstance(v, int) else v for v in tri]
            self.vertices.extend((v.x+self.ox, -v.y-self.oy, self.layer * .01) for v in coords)
            self.faces.append((start, start+1, start+2))
            self.colors.append(index)
        if stroke:
            self.line(points, stroke, width, closed=True)

    def line(self, points, color=INK, width=2, smooth=False, closed=False):
        if smooth:
            points = catmull(points, closed, 5)
        n = len(points)
        # One continuous ribbon prevents visible joints and retains editable polygons.
        left, right = [], []
        for i, p in enumerate(points):
            before = points[(i-1) % n] if i or closed else points[0]
            after = points[(i+1) % n] if i < n-1 or closed else points[-1]
            dx, dy = after[0]-before[0], after[1]-before[1]
            length = max(.001, math.hypot(dx, dy))
            nx, ny = -dy/length*width*.5, dx/length*width*.5
            left.append((p[0]+nx, p[1]+ny))
            right.append((p[0]-nx, p[1]-ny))
        for i in range(n if closed else n-1):
            j = (i + 1) % n
            self.poly([left[i], right[i], right[j], left[j]], color)

    def oval(self, x, y, rx, ry, color, stroke=None, width=2, angle=0):
        ca, sa = math.cos(angle), math.sin(angle)
        p = []
        for i in range(32):
            a = math.tau * i / 32
            px, py = rx*math.cos(a), ry*math.sin(a)
            p.append((x+px*ca-py*sa, y+px*sa+py*ca))
        self.poly(p, color, stroke, width)

    def finish(self):
        mesh = bpy.data.meshes.new(self.name + " inked layers")
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.update()
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        for c in self.palette:
            mesh.materials.append(material(c))
        for p, index in zip(mesh.polygons, self.colors):
            p.material_index = index
        obj["authoring"] = "Flat cel polygon cutout; layers ordered on local Z"
        return obj


SPIKES = [(21,77),(14,62),(18,53),(10,54),(18,42),(13,40),(29,34),(22,31),(34,25),
          (36,13),(43,23),(55,7),(54,21),(75,3),(72,19),(94,16),(118,7),(111,27),
          (102,34),(119,39),(108,46),(122,52),(107,60),(114,73),(94,69),(79,58),
          (67,45),(58,58),(46,68),(35,66),(30,87)]


def hair(d, style, base, mid, light):
    if style in ("bald", "baldbeard"):
        d.line([(37,48),(43,36),(56,31)], "#F9D4A0", 2.3, smooth=True)
        return
    if style in ("spikes", "dragon", "fox", "ninja", "sun", "tied", "tech"):
        points = SPIKES
        if style == "dragon":
            points = [(24,79),(13,57),(2,49),(20,44),(7,26),(31,34),(27,8),(48,26),
                      (55,2),(69,27),(86,6),(88,27),(119,14),(103,40),(125,44),(105,58),
                      (113,72),(94,65),(78,51),(67,44),(54,60),(39,66),(30,85)]
        elif style == "fox":
            points = [(23,76),(13,62),(19,51),(8,44),(28,39),(18,24),(38,29),(36,9),
                      (53,24),(63,6),(71,23),(91,9),(91,29),(113,22),(103,42),(123,45),
                      (108,57),(111,73),(93,65),(74,57),(56,57),(36,68),(29,84)]
        elif style == "tech":
            points = [(23,77),(21,37),(32,25),(37,15),(83,14),(103,28),(107,66),
                      (96,60),(84,48),(40,49),(31,79)]
        elif style == "tied":
            d.poly([(27,41),(8,29),(11,18),(21,27),(24,4),(34,17),(39,32)], base, INK)
        elif style == "sun":
            points = [(23,87),(10,94),(17,71),(5,64),(20,50),(13,32),(31,34),(30,13),
                      (49,22),(64,3),(74,21),(97,8),(94,32),(116,27),(105,48),(123,58),
                      (107,67),(118,91),(100,83),(86,58),(70,45),(56,65),(35,70)]
        d.poly(points, base, INK, 2.7)
        d.poly([(24,43),(43,31),(44,24),(55,30),(68,15),(64,29),(97,22),(88,32),
                (99,39),(78,36),(64,41),(51,37),(37,49)], mid)
        d.poly([(36,56),(47,46),(54,42),(48,54),(38,63)], mid)
        d.poly([(75,45),(95,51),(107,64),(94,60),(84,53)], mid)
        if style == "spikes":
            d.poly([(67,42),(77,46),(86,51),(101,59),(110,69),(93,64),(78,54)], light, INK, 1.0)
            d.poly([(72,45),(82,49),(90,54),(83,52)], "#FFC277")
        elif style in ("fox", "ninja", "sun", "tech", "dragon"):
            d.poly([(61,24),(70,18),(65,32),(79,29),(71,39),(54,38)], light)
    elif style == "bob":
        d.poly([(21,94),(15,76),(18,44),(26,25),(47,16),(75,19),(94,30),(104,53),
                (111,91),(102,107),(96,79),(81,47),(70,54),(52,54),(37,67),(29,104)], base, INK, 2.7, True)
        d.poly([(27,54),(32,35),(53,25),(78,28),(87,37),(58,34),(44,43),(36,69)], mid, smooth=True)
        d.poly([(88,48),(96,58),(101,90),(94,78)], light)
    elif style in ("crop", "mohawk", "baldbeard", "quiff", "slick", "beard", "bandana", "visor", "clown", "wave"):
        if style == "mohawk":
            d.poly([(42,50),(39,24),(48,10),(56,21),(65,5),(72,21),(82,14),(86,31),(78,51)], base, INK, 2.7)
            d.poly([(50,27),(56,19),(61,30),(67,16),(73,32),(64,45),(53,43)], mid)
        elif style == "clown":
            for x in (20,104):
                d.poly([(x-9,71),(x-16,54),(x-10,39),(x-14,24),(x,29),(x+6,17),
                        (x+13,36),(x+10,61)], base, INK, 2.5, True)
                d.poly([(x-8,44),(x-5,33),(x+2,35),(x+7,27),(x+8,46)], mid)
        elif style == "wave":
            d.poly([(23,79),(14,55),(21,37),(37,23),(58,18),(77,9),(79,22),
                    (105,18),(99,35),(116,38),(104,52),(98,75),(81,51),(68,42),(51,57),(31,65)], base, INK, 2.7, True)
            d.poly([(25,48),(42,33),(65,28),(88,21),(81,34),(99,32),(85,43),(62,37),(43,42)], mid, smooth=True)
            d.line([(36,41),(55,31),(74,32)], light, 2.1, smooth=True)
        else:
            top = [(23,75),(19,49),(25,35),(35,25),(50,23),(69,28),(84,22),(103,31),
                   (105,54),(96,65),(82,46),(56,47),(40,45),(30,78)]
            if style in ("quiff", "slick"):
                top = [(23,77),(19,46),(31,31),(48,27),(57,15),(75,20),(104,15),
                       (112,23),(105,40),(84,49),(54,43),(33,53),(30,80)]
            elif style == "beard":
                top = [(23,80),(16,58),(23,45),(17,37),(35,31),(34,18),(48,25),
                       (62,18),(78,27),(98,23),(106,41),(100,67),(86,57),(71,40),(50,53),(31,70)]
            d.poly(top, base, INK, 2.7)
            d.poly([(29,44),(41,34),(57,33),(70,28),(94,26),(85,37),(62,39),(47,36)], mid)
            d.line([(40,35),(62,31),(85,29)], light, 1.5, smooth=True)


def accessories(d, char, style, base, mid, accent):
    if style in ("cap", "patrol", "straw"):
        c = "#D9AF63" if style == "straw" else base
        hi = "#F2D790" if style == "straw" else mid
        d.poly([(22,54),(25,30),(40,20),(82,19),(103,31),(106,55)], c, INK, 2.7, True)
        d.poly([(28,33),(46,25),(82,25),(97,34),(82,31),(45,32)], hi)
        if style == "straw":
            d.poly([(25,47),(104,47),(107,56),(22,56)], accent, INK, 1.2)
            d.poly([(9,54),(44,51),(106,52),(122,60),(106,67),(32,64)], "#E7C17B", INK, 2.6, True)
            for x in (24,36,48,60,72,84,96,108):
                d.line([(x,57),(x+3,62)], "#AE8450", .9)
        else:
            d.poly([(30,50),(99,49),(116,58),(102,65),(54,58),(29,59)], mid, INK, 2.4)
            d.poly([(58,33),(65,29),(72,34),(70,43),(63,46),(57,41)], accent, INK, 1.2)
    if style in ("tied", "ninja", "fox", "bandana"):
        color = "#D34B46" if style in ("tied", "bandana") else "#2C3A51"
        d.poly([(25,55),(39,48),(72,51),(101,48),(104,63),(72,63),(41,59),(25,67)], color, INK, 2)
        d.poly([(47,52),(81,54),(81,62),(47,60)], "#A8B6C7", INK, 1.2)
        d.line([(59,55),(65,54),(70,58),(64,60),(61,57),(69,56)], INK, 1)
        if style in ("tied", "bandana"):
            d.poly([(24,58),(10,65),(3,80),(20,73),(8,94),(29,75)], color, INK, 1.8)
    if style == "tech":
        d.poly([(20,63),(29,58),(34,66),(31,82),(23,84),(18,77)], "#526572", INK, 1.8)
        d.poly([(23,67),(28,65),(29,77),(24,80)], accent)
    if style == "wave":
        d.poly([(22,75),(9,69),(15,85),(5,87),(23,99),(28,91)], "#58B4B1", INK, 2)
        d.line([(12,81),(22,87)], "#B0E5D3", 1.7)
    if char.startswith("naruto"):
        for yy in (94,100,106):
            d.line([(34,yy),(43,yy+2)], "#926450", 1)
            d.line([(94,yy),(103,yy-2)], "#926450", 1)
    if char == "savage":
        d.line([(89,59),(83,72),(87,87)], "#DFB598", 2.8)
        d.line([(88,62),(84,73),(88,87)], "#785044", 1)
    if char == "luffy":
        d.line([(84,100),(97,100)], "#915C49", 1.4)
        for x in (87,93):
            d.line([(x,97),(x+1,103)], "#915C49", 1.2)


def eye(d, x, y, iris, expression, right=False):
    if expression == "DIZZY_SPIRAL_HURT":
        pts = []
        for i in range(52):
            t = i / 51 * math.pi * 4.4
            r = .6 + i/51 * 7.5
            pts.append((x+math.cos(t)*r, y+math.sin(t)*r))
        d.line(pts, INK, 2.2)
    elif expression == "KO_STARS":
        d.line([(x-7,y-5),(x+6,y+5)], INK, 2.5)
        d.line([(x-6,y+5),(x+7,y-5)], INK, 2.5)
    elif expression in ("ECSTATIC_VICTORY_LAUGH", "BLINK"):
        d.line([(x-8,y+1),(x-5,y-4),(x,y-6),(x+5,y-4),(x+8,y+1)], INK, 3, True)
    else:
        glare = expression in ("BLAZING_GLARE", "WIDE_MOUTH_SHOUT")
        if right:
            shape = [(x-9,y-5),(x+7,y-9),(x+10,y-3),(x+8,y+7),(x+1,y+11),(x-7,y+8)]
        else:
            shape = [(x-10,y-8),(x+7,y-5),(x+9,y+4),(x+4,y+12),(x-4,y+11),(x-9,y+6)]
        if glare:
            shape = [(px, py + (2 if i < 2 else 0)) for i,(px,py) in enumerate(shape)]
        d.poly(shape, WHITE, INK, 1.7, True)
        eye_color = "#F7C83C" if expression == "BLAZING_GLARE" else iris
        d.oval(x+1.5, y+3, 5.2, 8.0, eye_color, INK, 1.3)
        d.oval(x+2.3, y+3, 2.7, 6.3, INK)
        d.oval(x+.3, y-.2, 2.0, 2.5, "#FFFFFF")
        d.oval(x+4, y+6.0, 1, 1.2, "#F9EACD")
        # Tapered top lash is a prominent, readable ink wedge.
        if right:
            d.poly([(x-10,y-5),(x+9,y-10),(x+12,y-9),(x+8,y-6),(x-7,y-3)], INK)
        else:
            d.poly([(x-11,y-10),(x+9,y-6),(x+10,y-3),(x-8,y-6)], INK)


def face(d, char, style, skin, shadow, iris, expression):
    for x in (24,104):
        d.oval(x, 84, 9, 13, skin, INK, 2.3, -.17 if x == 24 else .17)
        d.line([(x-2,79),(x+3,81),(x+3,90),(x,87)], shadow, 2.6, True)
    d.poly([(28,59),(33,43),(48,29),(71,27),(91,37),(103,55),(106,78),(103,95),
            (94,108),(77,118),(63,120),(47,114),(34,104),(27,88)], skin, INK, 2.8, True)
    d.poly([(31,60),(35,81),(38,98),(49,109),(66,116),(78,116),(64,120),(47,114),
            (34,103),(28,86)], shadow, smooth=True)
    d.poly([(93,49),(102,64),(103,86),(97,96),(98,76)], "#E5A57B" if skin == "#F8C78E" else shadow, smooth=True)
    d.oval(48,99,7,2.8,"#EBA78A")
    d.oval(94,96,5.5,2.5,"#EBA78A")
    if style in ("beard", "baldbeard"):
        c = STYLES[char][1]
        d.poly([(31,90),(40,98),(48,99),(57,103),(74,102),(90,97),(102,88),
                (100,106),(90,116),(72,124),(54,120),(40,110)], c, INK, 2.1)
        d.poly([(44,105),(57,111),(76,113),(91,105),(86,115),(70,120),(54,116)], STYLES[char][2])
    eye(d, 48, 82, iris, expression)
    eye(d, 86, 80, iris, expression, True)
    if expression in ("BLAZING_GLARE", "WIDE_MOUTH_SHOUT"):
        d.poly([(35,67),(41,65),(59,74),(57,77),(44,72)], INK)
        d.poly([(75,74),(90,63),(98,62),(95,68),(79,77)], INK)
    elif expression == "LOW_HP_SWEAT":
        d.line([(36,69),(44,65),(57,68)], INK, 2.4, True)
        d.line([(76,68),(88,65),(97,68)], INK, 2.4, True)
        d.poly([(109,73),(104,84),(105,89),(110,91),(114,87),(113,82)], "#92DDEA", INK, 1.2, True)
        d.line([(109,80),(108,85)], "#EDFCFF", 1.5)
    else:
        d.poly([(36,69),(43,66),(57,70),(58,73),(43,71)], INK)
        d.poly([(76,69),(89,63),(97,64),(97,67),(79,72)], INK)
    d.line([(68,88),(65,96),(69,98),(73,96)], shadow, 1.5, True)
    d.line([(67,95),(70,96)], INK, 1)
    if expression == "ECSTATIC_VICTORY_LAUGH":
        d.poly([(47,101),(67,105),(89,99),(85,113),(73,119),(61,117),(52,111)], "#602B35", INK, 2.1, True)
        d.poly([(49,102),(67,106),(88,101),(84,107),(55,108)], WHITE)
        d.poly([(61,115),(73,110),(84,111),(77,117),(67,118)], "#EE8A89", smooth=True)
    elif expression == "WIDE_MOUTH_SHOUT":
        d.poly([(57,102),(70,100),(81,105),(84,116),(75,120),(61,118),(54,112)], "#662E37", INK, 2, True)
        d.poly([(58,103),(71,102),(79,106),(78,110),(58,109)], WHITE)
        d.poly([(60,115),(69,112),(80,115),(75,118),(65,117)], "#EF9292", smooth=True)
    elif expression == "DIZZY_SPIRAL_HURT":
        d.poly([(50,109),(58,104),(69,109),(78,105),(86,111),(81,115),(70,113),(58,116)], "#BF6F74", INK, 1.6, True)
    elif expression == "KO_STARS":
        d.oval(69,110,8,5,"#8D5354",INK,1.4)
        for x,y in ((18,25),(111,22)):
            d.poly([(x,y-8),(x+2,y-2),(x+8,y-2),(x+3,y+2),(x+5,y+8),
                    (x,y+4),(x-5,y+8),(x-3,y+2),(x-8,y-2),(x-2,y-2)], "#F9D874", INK, 1.2)
    elif expression == "BLAZING_GLARE":
        d.line([(58,110),(65,108),(78,110)], INK, 1.9, True)
    elif expression == "LOW_HP_SWEAT":
        d.line([(55,111),(62,108),(76,109),(82,112)], INK, 1.9, True)
    else:
        d.line([(54,105),(61,109),(72,110),(83,105)], INK, 1.9, True)
        d.line([(82,102),(83,106),(87,107)], shadow, 1.3, True)
    if char == "funnyman":
        d.oval(68,97,7,5,"#D74B57",INK,1.4)
        d.oval(66,95,2,1.3,"#FFB6AF")
    if style == "quiff":
        d.poly([(59,115),(69,119),(80,113),(77,121),(68,124),(62,120)], STYLES[char][1], INK, 1)
    if style in ("visor", "slick"):
        c = "#30556C" if style == "visor" else "#202A3B"
        d.poly([(33,75),(59,76),(64,81),(72,80),(77,74),(100,71),(99,85),(88,91),
                (77,87),(73,83),(64,84),(58,91),(43,91),(36,85)], c, INK, 2)
        d.line([(39,78),(54,79)], "#8FD1DC", 1.8)
        d.line([(80,78),(95,75)], "#8FD1DC", 1.8)
        if expression == "DIZZY_SPIRAL_HURT":
            d.line([(40,80),(55,86),(43,87),(52,79)], "#E6EDDC", 1.1)


def render_heads():
    started = time.monotonic()
    compiled = json.loads((ROOT / "data/sf_compiled_rigs.json").read_text(encoding="utf-8"))
    current = set(compiled["characters"])
    current.update(json.loads(p.read_text(encoding="utf-8"))["id"] for p in (ROOT / "data/custom_fighters").glob("*.json"))
    if current != set(ROSTER):
        raise RuntimeError(f"Roster changed; missing authored identities {current-set(ROSTER)}, retired {set(ROSTER)-current}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.context.preferences.filepaths.save_version = 0
    for row, char in enumerate(ALL_ROWS):
        style, base, mid, accent, skin, shadow, iris = STYLES[char]
        for col, expression in enumerate(EXPRESSIONS):
            d = Drawing(f"{row:02d}_{char}__{expression}", col, row)
            face(d, char, style, skin, shadow, iris, expression)
            hair(d, style, base, mid, accent)
            accessories(d, char, style, base, mid, accent)
            obj = d.finish()
            obj["character_id"], obj["expression"] = char, expression
            obj["cell_px"] = [col*CELL, row*CELL, CELL, CELL]
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = CELL * len(EXPRESSIONS)
    scene.render.resolution_y = CELL * len(ALL_ROWS)
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 25
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.world.color = (0,0,0)
    camera = bpy.data.cameras.new("Atlas orthographic pixel camera")
    camera.type = "ORTHO"
    camera.ortho_scale = scene.render.resolution_y
    camera.clip_end = 3000
    obj = bpy.data.objects.new("Atlas orthographic pixel camera", camera)
    bpy.context.collection.objects.link(obj)
    obj.location = (scene.render.resolution_x/2, -scene.render.resolution_y/2, 1000)
    scene.camera = obj
    scene["authoring_medium"] = "Blender emissive layered planar cel meshes"
    scene["palette"] = "Warm skin / deep navy ink / deliberately asymmetric hair topology"
    scene["calibration"] = "128px / 10wu; skull reference y27..119; skull pivot=(64,73)"
    OUT.mkdir(parents=True, exist_ok=True)
    ART.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".build-", dir=OUT))
    try:
        scene.render.filepath = str(stage / "head_atlas.png")
        bpy.ops.render.render(write_still=True)
        # A second view of the same authored scene is useful for close visual review.
        scene.render.use_border = True
        scene.render.use_crop_to_border = True
        scene.render.border_min_x = 0
        scene.render.border_max_x = 1
        scene.render.border_min_y = (len(ALL_ROWS)-1)/len(ALL_ROWS)
        scene.render.border_max_y = 1
        scene.render.filepath = str(stage / "johnny_expression_board.png")
        bpy.ops.render.render(write_still=True)
        scene.render.use_border = False
        scene.render.use_crop_to_border = False
        scene.render.filepath = "//../../assets/sprites/chibi_brawler/r5_heads/head_atlas.png"
        blend_stage = ART / ".chibi_r5_heads.build.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_stage), check_existing=False)
        manifest = {
            "schema": "hh.chibi_blender_head_atlas.v1", "revision": "R5", "author": "HH Game Studio / Codex",
            "geometry_authorship": "Original polygon/curve geometry authored by HH Game Studio / Codex",
            "usage_scope": "Internal art study; recognizable third-party character designs have no assessed public-release clearance",
            "authoring_tool": "Blender " + bpy.app.version_string,
            "medium": "Editable layered planar meshes, emission cel materials, orthographic render",
            "source_blend": "res://art/chibi_r5/chibi_r5_heads.blend",
            "atlas": "res://assets/sprites/chibi_brawler/r5_heads/head_atlas.png",
            "image": "head_atlas.png", "width": len(EXPRESSIONS)*128, "height": len(ALL_ROWS)*128,
            "cell_size": 128, "atlas_size": [len(EXPRESSIONS)*128,len(ALL_ROWS)*128], "columns": len(EXPRESSIONS), "rows": len(ALL_ROWS),
            "generation": "R5.blender.cel.heads.2", "expressions": [ex.lower() for ex in EXPRESSIONS],
            "characters": ALL_ROWS, "character_order": ALL_ROWS, "base_characters": ROSTER,
            "transformation_rows": EXTRA_ROWS,
            "facing": "right; runtime may mirror whole cell for left",
            "units_per_pixel": 10/128, "pivot_px": [64,73],
            "world_rect_relative_to_skull_center": [-5,-73*10/128,10,10],
            "skull_reference_rect_px": [20,27,88,92], "skull_reference_height_world": 92*10/128,
            "neck_anchor_px": [66,119], "hair_max_extension_world": 24*10/128,
            "cells": {char: {ex.lower(): {"rect": [col*128,row*128,128,128], "pivot": [64,73]}
                       for col,ex in enumerate(EXPRESSIONS)} for row,char in enumerate(ALL_ROWS)},
            "identity_topology": {char: STYLES[char][0] for char in ALL_ROWS},
            "script_sha256": digest(__file__), "blend_sha256": digest(blend_stage),
            "atlas_sha256": digest(stage/"head_atlas.png"),
            "reference_sheet_sha256": digest(ROOT/"assets/sheets/chibi_brawler_master_sheet.jpg"),
            "reference_use": "Visual art direction only; no pixels extracted or bundled in this atlas",
            "render_elapsed_seconds": round(time.monotonic()-started,3),
            "art_acceptance": "Requires in-game size and human aesthetic review; render completion alone is not acceptance",
        }
        (stage/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n",encoding="utf-8")
        for name in ("head_atlas.png", "johnny_expression_board.png", "manifest.json"):
            os.replace(stage/name, OUT/name)
        os.replace(blend_stage, ART/"chibi_r5_heads.blend")
        print("CHIBI_R5_HEADS_RENDER_OK " + json.dumps({"atlas":str(OUT/"head_atlas.png"),
              "sha256":manifest["atlas_sha256"],"cells":len(ALL_ROWS)*len(EXPRESSIONS),"seconds":manifest["render_elapsed_seconds"]}))
    finally:
        shutil.rmtree(stage)


if __name__ == "__main__":
    render_heads()
