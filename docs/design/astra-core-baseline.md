# Astra Core design baseline

The owner accepted the Astra glass orb at commit
`09105917565390f253e88207f34dcd028483fe12` as Orion's Core design baseline.
This is a product identity asset. Future work should refine this design.

## Protected structure

- One continuous dark glass sphere, with separate edge illumination, restrained
  surface reflections and an illuminated orbital rim.
- Two fixed eye apertures. The aperture, bloom silhouette and stationary clip
  reference the same eye geometry; only the luminous content inside moves with gaze.
- Separate stationary blink masks enclose both sharp light and bloom. Shutters
  operate inside those masks, never as opaque shapes painted over the face.
- An addressable inline SVG remains connected to the production presence
  controller, including blink interruption, runtime state and reduced motion.
- The vertical light beam removed at the baseline must not return through the
  ORION name, state, tagline or detail text.

Do not reintroduce a forehead blob, lower-face patch, closed face-plane/mask
construction, a flattened face image, or gaze that slides the entire eye assembly.
Do not replace the masked-eye architecture without a concrete problem demonstrated
in rendered review. Any necessary architectural change should explain that problem
and preserve the accepted identity.

## Next refinements

Refine the neutral eye expression, rim/highlight balance, scale and placement in
the hero, and the orb's interaction with environment lighting. Eye path coordinates,
gradient colors, stroke widths, highlight intensity and placement are art parameters,
not frozen identity constants. Adjust them through rendered comparison with the
accepted baseline; preserve the structure above.

## Purposeful attention

Neutral remains the resting pose. Brief glances may acknowledge a submitted turn,
the first visible reply text or completed response, a newly presented summon, a
failed tool activity, or an approval needing the operator's decision. Directions
come from visible screen geometry, not a fixed mapping from operational state.
Approval takes priority over ordinary conversation cues. Glances return to neutral
after 1.2 seconds (1.8 seconds for approval), with a 2.6-second cooldown that a new
higher-priority cue can interrupt. No random scanning or per-token gaze changes.
Reduced motion, an invisible page/Core, offscreen targets and OFFLINE suppress
attention. The masked-eye architecture remains unchanged.

Keep the moving light visibly distinct from the aperture: a compact bright center
against a dimmer cyan opening, with restrained bloom. Review normal conversation
attention as well as the manual left/right poses when tuning contrast and travel.

## Verification

`hud/tests/test_astra_core_identity.py` checks the actual SVG structure and reference
relationships. Its deliberate broken examples must fail validation: a renamed face
patch, a closed patch hidden among reflections, a non-spherical surface, a clip
moved with gaze, bloom outside its blink mask, and a visible lid overlay.
It also rejects an aperture and its clip referencing different shapes, while a
positive refinement case demonstrates that art parameters can still change.

`hud/tests/capture_ui_visuals.py` exercises the production renderer. It verifies
stationary apertures and moving internal light, checks bright eye pixels disappear
on full closure and return on reopening, tests interruption and reduced motion,
and records real-time motion. These checks complement visual judgment; they do not
prove an expression or lighting treatment looks good.

Review neutral, left/right gaze, blink and reopening, WAITING, OFFLINE and reduced
motion in `?fixture=core-review`, plus the populated desktop, approval and mobile
fixtures. Check name/tagline readability and scene integration at actual display
sizes. Retain screenshots and a motion recording with each visual refinement.

Structural test failures are a reason to investigate a regression, not to delete
the contract during cleanup. Update art-specific assertions deliberately when a
rendered refinement warrants it; keep the identity and behavior checks intact.
