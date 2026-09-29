"""Protect the approved Astra structure without freezing its art parameters.

See docs/design/astra-core-baseline.md. Mutation cases prove that renamed
face patches and broken clipping/masking cannot pass by retaining CSS names.
"""
from copy import deepcopy
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


def core_svg():
    html = (Path(__file__).resolve().parents[1] / "static/index.html").read_text(encoding="utf-8")
    match = re.search(r'<svg\b[^>]*class="[^"]*\bcore-orb\b[^"]*"[^>]*>.*?</svg>', html, re.S)
    if not match:
        raise AssertionError("Astra must remain an addressable inline SVG")
    return ET.fromstring(match.group())


def role(root, name):
    matches = [node for node in root.iter() if name in node.get("class", "").split()]
    if len(matches) != 1:
        raise AssertionError(f"Expected one {name}, found {len(matches)}")
    return matches[0]


class AstraCoreIdentityTests(unittest.TestCase):
    def assert_identity(self, core):
        self.assertEqual(core.tag, "svg")
        self.assertFalse(list(core.iter("image")), "Do not flatten the live Core to an image")
        self.assertFalse(list(core.iter("foreignObject")))
        defs = core.find("defs")
        self.assertIsNotNone(defs)
        halo, face = role(core, "core-halo-group"), role(core, "core-face-group")
        self.assertEqual(set(core), {defs, halo, face}, "Unexpected Core overlay")

        glass, edge = role(core, "core-face"), role(core, "core-surface-edge")
        depth, rim = role(core, "core-surface-depth"), role(core, "core-inner-rim")
        eyes = [role(core, f"core-eye-{side}") for side in ("left", "right")]
        self.assertEqual(set(face), {glass, edge, depth, rim, *eyes}, "Unexpected face patch")
        geometry = {key: glass.get(key) for key in ("cx", "cy", "r")}
        for layer in (glass, edge):
            self.assertEqual(layer.tag, "circle", "The surface must remain a continuous sphere")
            self.assertEqual({key: layer.get(key) for key in geometry}, geometry)
        self.assertEqual(glass.get("fill"), "url(#coreGlass)")
        self.assertIsNotNone(defs.find('./radialGradient[@id="coreGlass"]'))
        self.assertEqual(edge.get("fill"), "url(#coreEdgeLight)")
        self.assertEqual(depth.get("clip-path"), "url(#coreSphereClip)")
        sphere_clip = defs.find('./clipPath[@id="coreSphereClip"]/circle')
        self.assertIsNotNone(sphere_clip)
        self.assertEqual({key: sphere_clip.get(key) for key in geometry}, geometry)

        # Surface accents may be light spill, open reflection strokes or tiny
        # stars. A renamed filled forehead/mask path is still a regression.
        for node in list(depth.iter())[1:]:
            if node.tag == "ellipse":
                self.assertEqual(node.get("fill"), "url(#coreLightSpill)")
            elif node.tag == "path":
                self.assertIn("core-glass-reflection", node.get("class", "").split())
                self.assertNotRegex(node.get("d", ""), "[zZ]", "No closed face planes")
                self.assertIn(node.get("fill"), (None, "none"))
            elif node.tag == "circle":
                self.assertLess(float(node.get("r")), float(glass.get("r")) * .02)
            else:
                self.assertEqual(node.tag, "g")
                self.assertIn("core-starlight", node.get("class", "").split())
        outer, bloom = role(halo, "core-halo-outer"), role(halo, "core-halo-bloom")
        for layer in (rim, outer, bloom):
            self.assertEqual(layer.tag, "circle")
            self.assertEqual((layer.get("cx"), layer.get("cy")), (glass.get("cx"), glass.get("cy")))
        self.assertGreater(float(outer.get("r")), float(glass.get("r")))
        self.assertEqual(outer.get("r"), bloom.get("r"))

        masked_lids = set()
        for side, eye in zip(("Left", "Right"), eyes):
            shutter = role(eye, "core-eye-shutter")
            self.assertEqual(set(eye), {shutter, role(eye, "core-eye-seam")})
            self.assertEqual(shutter.get("mask"), f"url(#coreLidMask{side})")
            mask = defs.find(f'./mask[@id="coreLidMask{side}"]')
            self.assertIsNotNone(mask)
            self.assertEqual(mask.get("maskUnits"), "userSpaceOnUse")
            lids = {role(mask, "core-eye-lid-top"), role(mask, "core-eye-lid-bottom")}
            self.assertTrue(all(lid.tag == "rect" for lid in lids))
            masked_lids.update(lids)

            aperture, glow = role(eye, "core-eye-aperture"), role(eye, "core-eye-bloom")
            window, content = role(eye, "core-eye-window"), role(eye, "core-eye-content")
            self.assertEqual(set(shutter), {aperture, glow, window}, "All eye light must be masked")
            self.assertEqual(list(window), [content], "Clip the stationary parent, not moving light")
            self.assertEqual(window.get("clip-path"), f"url(#coreEyeClip{side})")
            self.assertIsNone(content.get("clip-path"))
            clip = defs.find(f'./clipPath[@id="coreEyeClip{side}"]')
            self.assertIsNotNone(clip)
            self.assertEqual(len(clip), 1)
            for use in (aperture, glow, clip[0]):
                self.assertEqual(use.tag, "use")
                self.assertEqual(use.get("href"), f"#coreEye{side}Shape")
            self.assertIsNotNone(defs.find(f'./path[@id="coreEye{side}Shape"]'))
            for fixed in (eye, shutter, aperture, window, clip, mask):
                self.assertIsNone(fixed.get("transform"), "Only internal eye light may follow gaze")
        all_lids = {node for node in core.iter() if "core-eye-lid" in node.get("class", "").split()}
        self.assertEqual(all_lids, masked_lids, "Lids belong in masks, never painted on the face")

    def test_production_astra_structure(self):
        self.assert_identity(core_svg())

    def test_allows_art_refinements_with_same_architecture(self):
        core = core_svg()
        core.find('./defs/path[@id="coreEyeLeftShape"]').set("d", "M86 148Q112 135 143 154Q112 169 86 148Z")
        core.find('./defs/radialGradient[@id="coreGlass"]/stop').set("stop-color", "#102331")
        role(core, "core-halo-outer").set("stroke-width", "1.4")
        role(core, "core-halo-bloom").set("opacity", ".25")
        self.assert_identity(core)

    def test_rejects_renamed_face_patch(self):
        core = core_svg()
        ET.SubElement(role(core, "core-face-group"), "path", {"class": "new-shading", "d": "M0 0H200V200Z", "fill": "black"})
        with self.assertRaisesRegex(AssertionError, "Unexpected face patch"):
            self.assert_identity(core)

    def test_rejects_closed_patch_hidden_in_surface_accents(self):
        core = core_svg()
        role(core, "core-glass-reflection").set("d", "M0 0H200V200Z")
        with self.assertRaisesRegex(AssertionError, "No closed face planes"):
            self.assert_identity(core)

    def test_rejects_non_spherical_surface(self):
        core = core_svg()
        role(core, "core-face").tag = "path"
        with self.assertRaisesRegex(AssertionError, "continuous sphere"):
            self.assert_identity(core)

    def test_rejects_clip_moved_onto_gaze_content(self):
        core = core_svg()
        eye = role(core, "core-eye-left")
        role(eye, "core-eye-content").set("clip-path", role(eye, "core-eye-window").attrib.pop("clip-path"))
        with self.assertRaises(AssertionError):
            self.assert_identity(core)

    def test_rejects_aperture_and_clip_using_different_shapes(self):
        core = core_svg()
        core.find('./defs/clipPath[@id="coreEyeClipLeft"]/use').set("href", "#coreEyeRightShape")
        with self.assertRaises(AssertionError):
            self.assert_identity(core)

    def test_rejects_bloom_outside_blink_mask(self):
        core = core_svg()
        eye = role(core, "core-eye-left")
        glow = role(eye, "core-eye-bloom")
        role(eye, "core-eye-shutter").remove(glow)
        eye.append(glow)
        with self.assertRaises(AssertionError):
            self.assert_identity(core)

    def test_rejects_visible_lid_overlay(self):
        core = core_svg()
        eye = role(core, "core-eye-left")
        eye.append(deepcopy(role(core.find('./defs/mask'), "core-eye-lid-top")))
        with self.assertRaises(AssertionError):
            self.assert_identity(core)


if __name__ == "__main__":
    unittest.main()
