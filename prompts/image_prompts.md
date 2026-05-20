# Image prompt library

This file defines the **image codes** that idea cards reference and that the polish skill uses to build image-generation prompts. You can edit it freely. Add your own codes, change descriptions, drop ones you don't use.

Each entry is a self-contained prompt the image generator will run with. Keep them visual, specific, and consistent in style if you want a recognizable look across your posts.

---

## Concept-only codes (no portrait, safe for any topic)

### `iso-architecture`

Isometric line drawing of a system architecture. Three layers stacked at 30 degrees. Thin white lines on deep blue background. No people, no logos, no text. Subtle gradient. Clean technical aesthetic. Editorial illustration style.

### `chalk-sketch`

Chalk-on-blackboard sketch of a mental model or framework. Simple shapes, arrows, hand-drawn feel. White chalk on dark slate. No people. A few keywords allowed but kept short. Loose, intentional, taught-on-a-whiteboard energy.

### `hero-line`

Bold single-line illustration. One continuous line forming an abstract shape (mountain, wave, signal, path). Solid accent color on neutral background. Editorial poster style. No text. High visual impact for opinion posts.

### `data-cards`

Stacked UI card composition. Three to five cards floating in space, each showing abstract data shapes (small charts, sparklines, metric pills). Soft drop shadows. Light background. Modern dashboard aesthetic. No real numbers or identifiable brands.

### `scene-photo`

Realistic editorial scene photo. A workspace, a quiet moment, an abstract setting that matches the post's mood. Cinematic lighting, natural color. No identifiable people in close-up. Camera 35mm, shallow depth of field.

---

## Custom codes (add your own)

If you want a personal portrait or a recurring character in your posts, add codes here. Examples of what users sometimes add:

### `working-close` (example)

Photo of a person at a desk, laptop open, soft lamp light, focused expression. Three-quarter angle. Editorial photo, 35mm, shallow depth of field. Matches the writer's likeness if a reference image is supplied.

### `speaking-stage` (example)

Speaker on a conference stage, mid-gesture, audience blurred in background. Stage lighting from above. Editorial photojournalism style. Matches the writer's likeness if a reference image is supplied.

---

## Notes for the polish skill

When polishing a post:

1. Read the `image_code` field on the idea card.
2. Find the matching section here.
3. Use the description as the base prompt.
4. Tune for the specific post: add 1-2 visual elements that connect to the post's hook or takeaway.
5. Pass the final prompt to `scripts/generate_image.py` (if configured).

Keep image generation **optional**. If `OPENAI_API_KEY` is not set in the environment, the polish skill should still produce the text post and skip image generation cleanly.
