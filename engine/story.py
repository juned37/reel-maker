PROMPT = """
Create an accurate, engaging documentary for vertical video.

TOPIC: {topic}
DURATION: {minutes} minutes.
TARGET NARRATION: {words} words.
ACCEPTABLE WORD RANGE: {minimum_words}-{maximum_words} words.

Return one valid JSON object only. No Markdown fences or explanations.

JSON structure:
{
  "title": ["Documentary title"],
  "watermark": "",
  "voice": "en-US-GuyNeural",
  "rate": "-3%",
  "claims_to_verify": [],
  "visual_style": "cinematic",
  "scenes": [
    {
      "onscreen_title": "Scene heading",
      "narration": "Spoken narration",
      "clear": true,
      "visual_brief": "Detailed description of the actual scene.",
      "show": ["book@left"],
      "visual_plan": {
        "elements": [
          {
            "type": "line",
            "points": [[15, 65], [50, 40], [85, 65]],
            "color": "gold",
            "width": 4,
            "draw_at": 0.2,
            "draw_duration": 0.5
          }
        ]
      },
      "camera": "slow_push",
      "transition": "crossfade",
      "source_notes": ""
    }
  ]
}

NARRATION:
- Write approximately {words} spoken words in total.
- Stay inside the acceptable word range.
- Divide narration across 8 to 12 scenes.
- Give every scene meaningful narration.
- Do not use one-sentence scenes merely to increase scene count.
- Open with a strong hook and end with a meaningful conclusion.
- Use natural spoken language.
- Avoid repetition and unsupported claims.

CINEMATIC VISUALS:
- Every scene must have its own detailed visual_brief.
- Describe the actual subject of that scene, not a generic symbol.
- Describe foreground, middle ground and background.
- Describe architecture, environment, objects, materials and lighting.
- Use the historically appropriate period and geographical setting.
- Make the visual_brief specific enough to guide an image-generation model.
- Keep a consistent cinematic hand-painted documentary art direction.
- Do not use web photographs.
- Do not request text, captions, letters or logos inside images.
- Do not repeat the same composition across scenes.
- Do not invent portraits of historical people.
- Use landscapes, architecture, objects, manuscripts, buildings and
  environments when depicting historical events.

HYBRID VECTOR VISUALS:
- visual_plan is optional.
- Use it when a map, timeline, route, scientific diagram, process,
  relationship or explanatory overlay would improve understanding.
- Do not create a vector plan merely for decoration.
- Use 3 to 12 elements for a useful diagram.
- Use only these types:
  line, path, polyline, polygon, arrow, circle, ellipse, rect, text, arc.
- Coordinates must be between 0 and 100.
- Use the supported colors:
  ink, gold, paper, pale, muted, blue, green, red, white, dark.
- Use draw_at and draw_duration between 0 and 1.
- Do not put long text inside a visual plan.
- Use short labels only when necessary.
- A visual plan must complement the scene artwork, not replace it.

LEGACY FALLBACK:
- show must remain a list of 0 to 2 supported art.py specifications.
- Use the catalogue only as a fallback for scenes without generated images.
- Use @left, @center or @right for positions.
- Do not use the same object in every scene without a narrative reason.

AVAILABLE ILLUSTRATIONS:
crescent, sun, book, mosque, kaaba, calendar, question,
hourglass, heart, lantern, globe, prayer_mat, beads, coins,
water_vessel, dates, minaret, dome, caravan, tent, scroll,
ship, palace, city_gate, map, compass, mountain, river,
atom, microscope, telescope, lightbulb, gears, computer,
ledger, marketplace, inkwell, arches, scale, figures.

ISLAMIC CONTENT AND HISTORICAL SAFEGUARDS:
- Never depict Prophet Muhammad ﷺ in any form, including silhouette,
  shadow or symbolic human representation.
- Never depict any named prophet.
- Do not invent portraits or appearances of historical people.
- Do not present imagined reconstructions as historical evidence.
- Avoid anachronistic clothing, objects and buildings.
- Distinguish established evidence, tradition and disputed reports.
- Do not invent quotations, dates or religious rulings.
- Put important uncertain claims in claims_to_verify.
- When a sacred figure is relevant, use the setting, architecture,
  landscape or objects without depicting the person.

FIELDS:
- clear must be true.
- camera must be slow_push, pan_left, pan_right, pan_up or pan_down.
- transition must be crossfade or cut.
- source_notes should identify evidence limitations when relevant.

Return valid JSON only. Ensure all braces, quotes and commas are
valid JSON syntax. Do not add comments or trailing commas.
"""
