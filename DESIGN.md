---
name: Claude Buddy
description: A pixel-art hillside where the buddy's critter acts out its mood, with game-HUD panels on top.
colors:
  critter-orange: "#d97757"
  critter-ink: "#2a1712"
  sticker-cream: "#fff8ee"
  mood-idle: "#a9b4f5"
  mood-working: "#ffd66b"
  mood-done: "#7fe0a8"
  mood-needs-you: "#ff86b0"
  mood-offline: "#9a9cad"
  mood-annoyed: "#ffa45c"
  mood-yelling: "#ff5f5f"
  stats-bar-soft: "#7a4535"
  critter-strawberry: "#e05a6d"
  critter-banana: "#f2c94c"
  critter-mint: "#5cc8b8"
  critter-blueberry: "#6b8fe6"
  critter-licorice: "#2e2b33"
  critter-marshmallow: "#efe7dc"
  hud-navy: "#11152a"
  hud-edge: "#0a0c1a"
  hud-rim: "rgb(255 255 255 / 0.14)"
  hud-ink: "#f5f3ec"
  hud-ink-soft: "#c8cbe6"
  ink-on-hue: "#14162a"
  stone-grey: "#6a6a6a"
  stone-hover: "#5c6494"
  stone-pressed: "#4f4f53"
  stone-disabled: "#333333"
  stone-edge: "#0e0e0e"
  stone-label: "#f2f2f2"
  stone-label-shadow: "#3b3b3b"
  signal-yellow: "#ffffa0"
  lcd-bezel: "#142009"
  lcd-glass: "#9cc23f"
  lcd-ink: "#13200a"
  field-black: "#000000"
  field-edge: "#a0a0a0"
  error-pink: "#ff6b8e"
  error-text: "#ffb3c8"
  sky-deep: "#1b4fc9"
  sky-blue: "#2f78e0"
  sky-haze: "#a9d1f7"
  grass-deep: "#1f5e17"
  grass-green: "#4fab25"
  grass-bright: "#a6e34d"
  alert-red: "#e0245e"
  bubble-ink: "#1c1f33"
typography:
  display:
    fontFamily: "Pixelify Sans, system-ui, sans-serif"
    fontSize: "38px"
    fontWeight: 700
    lineHeight: 1
  headline:
    fontFamily: "Pixelify Sans, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.35
  body:
    fontFamily: "Pixelify Sans, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.35
  label:
    fontFamily: "Pixelify Sans, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: 1
  caption:
    fontFamily: "Pixelify Sans, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.35
  lcd:
    fontFamily: "VT323, ui-monospace, monospace"
    fontSize: "26px"
    fontWeight: 400
    lineHeight: 1.05
  lcd-input:
    fontFamily: "VT323, ui-monospace, monospace"
    fontSize: "24px"
    fontWeight: 400
    lineHeight: 1
rounded:
  none: "0px"
spacing:
  pixel: "2px"
  xs: "4px"
  sm: "8px"
  gutter: "10px"
  md: "12px"
  lg: "16px"
  edge: "20px"
components:
  button-stone:
    backgroundColor: "{colors.stone-grey}"
    textColor: "{colors.stone-label}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 18px"
    height: "44px"
  button-stone-hover:
    backgroundColor: "{colors.stone-hover}"
    textColor: "{colors.signal-yellow}"
  button-stone-pressed:
    backgroundColor: "{colors.stone-pressed}"
    textColor: "{colors.stone-label}"
  button-stone-disabled:
    backgroundColor: "{colors.stone-disabled}"
  button-mood:
    backgroundColor: "{colors.stone-grey}"
    textColor: "{colors.stone-label}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "6px 12px"
    height: "52px"
  hud-panel:
    backgroundColor: "{colors.hud-navy}"
    textColor: "{colors.hud-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "16px 18px"
  lcd-screen:
    backgroundColor: "{colors.lcd-glass}"
    textColor: "{colors.lcd-ink}"
    typography: "{typography.lcd}"
    rounded: "{rounded.none}"
    padding: "6px"
  input-lcd:
    backgroundColor: "{colors.field-black}"
    typography: "{typography.lcd-input}"
    rounded: "{rounded.none}"
    padding: "0 10px"
    height: "40px"
  seen-flag:
    textColor: "{colors.ink-on-hue}"
    typography: "{typography.caption}"
    rounded: "{rounded.none}"
    padding: "3px 8px"
---

# Design System: Claude Buddy

## Overview

**Creative North Star: "The Sticker on the Hillside"**

The whole page is one pixel-art desktop-wallpaper landscape: a bright-green rolling hill under a dithered deep-blue sky with drifting pixel clouds, painted on a single low-resolution canvas (150 to 220 internal pixels tall) and scaled up crisp with no smoothing. On the hill crest walks the orange pixel critter, outlined with a one-pixel cream die-cut rim so it reads as a sticker slapped onto the scene. The critter's face and behaviour are the mood; the interface is secondary and stays small.

The UI floats on the landscape as dark navy game-HUD panels with a pixel typeface throughout, and every control is a grey bevelled stone button with a generated pixel-noise texture. Each mood owns exactly one full-strength hue, which appears as the panel's top band, the mood name, the time-in-mood bar and the pressed button's underline. Everything is square-cornered; depth comes from bevels, hard borders and one soft drop under the panels. The page never scrolls.

This is a homage world, not a copy: no Bliss photograph, no Minecraft textures or fonts, no OS window chrome. The landscape, the stone noise and the critter are all generated in code.

**Key Characteristics:**
- One full-bleed, low-res canvas scaled with `image-rendering: pixelated`; 4x4 Bayer dithering for every gradient.
- The critter is the mood: face plus behaviour, never hue alone.
- Dark navy HUD panels with a mood-hue top band.
- Grey bevelled stone buttons with pixel noise; blue-tinted hover; sunken pressed state for the current mood.
- Pixelify Sans for all UI text, VT323 only for LCD characters.
- Zero radius everywhere.

## Colors

A saturated wallpaper landscape behind a near-black navy HUD, with four mood hues as the only bright UI colours.

### Primary
- **Claude Clay Orange** (critter-orange): the critter's body, in the brand mascot's spirit. It appears only in the critter sprite and its small face icons, never as a UI fill.
- **Sticker Cream** (sticker-cream): the one-pixel die-cut rim drawn around the critter on the scene. It is what makes the critter a sticker.
- **Critter Ink** (critter-ink): the critter's eyes. It has no mouth: every mood shows through the eyes, arms and behaviour alone.

### Critter colours

The user picks the critter's body colour in Settings from eight squares: Claude orange (the default) and six presets (critter-strawberry, critter-banana, critter-mint, critter-blueberry, critter-licorice, critter-marshmallow; only Licorice gets light eyes), plus a rainbow square that opens a pixel colour wheel (hue around the wheel, strength from the grey centre to the edge, brightness fixed at 0.85 so the eyes stay readable). The shade and highlight come from the chosen colour. The choice is saved in the browser only.

### Secondary: the mood hues
- **Periwinkle** (mood-idle): IDLE.
- **Butter Yellow** (mood-working): WORKING.
- **Mint** (mood-done): DONE.
- **Hot Pink** (mood-needs-you): NEEDS_YOU.
- **Warning Orange** (mood-annoyed) and **Alarm Red** (mood-yelling): ANNOYED and YELLING, the two nag-timer moods.
- **Slate** (mood-offline): replaces the mood hue when the service is unreachable.

The active hue is a single live value (`--hue`) switched on `body[data-mood]`. It drives the panel's top band, the mood name, lit time-bar steps, the seen flag and text selection. Text on a hue fill is Ink on Hue (ink-on-hue).

### Tertiary: the landscape
- **Sky** (sky-deep to sky-haze, seven steps, sky-blue mid): dithered vertical gradient, also the page background before the canvas paints.
- **Grass** (grass-deep to grass-bright, seven steps): the hill and foreground field, dithered.
- **Alert Red** (alert-red) and **Bubble Ink** (bubble-ink): the emote speech bubble's "!" and its outline.

### Neutral
- **HUD Navy** (hud-navy): every panel surface. **HUD Edge** (hud-edge): its 3px outer border. **HUD Rim** (hud-rim): the 2px inner light line.
- **Warm Paper Ink** (hud-ink): primary text on panels. **Lavender Mist** (hud-ink-soft): secondary text, hints, counters.
- **Stone Grey / Dusk Stone / Pressed Stone / Dead Stone** (stone-grey, stone-hover, stone-pressed, stone-disabled): the button surface states; **Stone Edge** (stone-edge) the 2px border; **Stone Label** (stone-label) with its **Label Shadow** (stone-label-shadow).
- **Signal Yellow** (signal-yellow): hover label, keyboard focus outline, text caret. The one interaction highlight.
- **LCD Bezel / LCD Glass / LCD Ink** (lcd-bezel, lcd-glass, lcd-ink): the 16-cell preview, a classic green character LCD.
- **Field Black / Field Edge** (field-black, field-edge): text inputs. **Error Pink** (error-pink) marks an invalid input's border; **Error Text** (error-text) carries the message.

### Named Rules
**The One Hue Per Mood Rule.** Each mood owns exactly one full-strength hue, and only the current mood's hue is lit on the HUD. Never mix two mood hues in one element.

**The Face Before Hue Rule.** A mood is always shown by the critter's face (and on the scene, its behaviour) alongside its name; colour alone never carries a mood.

**The Orange Is Alive Rule.** Clay orange belongs to the critter. It is never a button, panel or text colour.

## Typography

**Display Font:** Pixelify Sans (with system-ui, sans-serif)
**Body Font:** Pixelify Sans (with system-ui, sans-serif)
**Label/Mono Font:** VT323 (with ui-monospace, monospace), for LCD characters only

**Character:** A chunky, readable pixel face for everything a person reads, and a dot-matrix terminal face reserved for what the physical buddy's 16-character LCD would show. Ligatures are off.

### Hierarchy
- **Display** (700, 38px, 1; 30px under 720px): the current mood name, coloured with the mood hue.
- **Headline** (700, 24px): panel headings such as the screen-messages editor.
- **Body** (400, 17px, 1.35): status lines, hints, form status.
- **Label** (500, 18px, 1): stone button text, with a 2px pixel drop of Label Shadow.
- **Caption** (400, 14px): character counters (tabular numerals), field errors, the seen flag (700, uppercase).
- **LCD** (VT323 26px, 1.05; 20px under 720px): one character per LCD cell. **LCD Input** (VT323 24px) for the message fields, so typing previews the device's own letterforms.

### Numbers

Every number in running text (timers, stats values, changes, times of day, character counts) is set in VT323 at 1.3em inside its line. Pixelify Sans draws 5 and S almost identically, which makes figures misreadable; words stay in Pixelify Sans.

### Named Rules
**The Screen Speaks VT323 Rule.** VT323 is used only for text that is, or previews, the buddy's LCD (cells, the message inputs, inline `code`). All other text is Pixelify Sans.

## Layout

The scene is `position: fixed` and full-bleed; the HUD is an overlay layer with no scroll (`overflow: hidden` on body). Desktop is primary.

- **Mood panel**: top-left, 20px from the edges, width up to 380px.
- **Settings toggle**: top-right stone button with a pixel gear, 20px inset. It is the only control on the main screen. Settings opens as a panel below it (top 80px, width up to 460px, scrolls internally if tall), with two sections divided by a rim rule: Claude's mood (2x2 mood buttons) and Screen messages (the editor).
- **Scene**: the hill crest sits left of centre on wide screens; the critter performs near the horizontal centre, at a pixel unit of 3 (2 on narrow canvases) so it reads from across the room.

Rhythm runs on small steps: 2px pixel gaps (time bar, LCD cells), 8 and 10px gaps between controls, 12 to 16px panel padding, a 20px viewport inset.

Under 720px the inset drops to 12px, the mood panel spans the width below the toggle, the settings panel covers the screen as an overlay, and on portrait screens the land is pushed down so the panel does not cover the hilltop.

## Elevation & Depth

Depth is game-HUD, not material: hard borders and bevels carry the form, and one soft drop lifts the panels off the landscape.

### Shadow Vocabulary
- **HUD lift** (`box-shadow: inset 0 0 0 2px rgb(255 255 255 / 0.14), 0 10px 24px rgb(0 0 0 / 0.3)`): every navy panel.
- **Stone bevel, raised** (`box-shadow: inset 2px 2px 0 rgb(255 255 255 / 0.42), inset -2px -3px 0 rgb(0 0 0 / 0.38)`): stone buttons at rest and on hover.
- **Stone bevel, sunken** (`box-shadow: inset 2px 3px 0 rgb(0 0 0 / 0.45), inset -2px -2px 0 rgb(255 255 255 / 0.18)`): pressed, and the current mood's button.
- **Label drop** (`text-shadow: 2px 2px 0 #3b3b3b`): stone button labels only.
- **Sticker rim**: the critter's one-pixel cream outline on the canvas, its only "shadow".

### Named Rules
**The Bevel Not Offset Rule.** Hard-edged depth lives inside the stone (inset bevels and the 2px label drop). Panels never take a hard offset block shadow; their only outer shadow is the soft HUD lift.

## Shapes

Every corner is square (0px): panels, buttons, inputs, the LCD, the time-bar steps and the seen flag. Edges are drawn with solid pixel-weight borders (2px on buttons, inputs and the LCD; 3px on panels). The only curves in the system are the hill and the clouds, and those are stepped in canvas pixels. The critter's silhouette is blocky and gets a single-pixel cream outline.

## Components

### Buttons
Tactile, chunky, game-menu stone.
- **Shape:** square (0px), 2px Stone Edge border, minimum 44px tall.
- **Stone (default):** Stone Grey under a 16x16 generated pixel-noise tile drawn at 32px with `image-rendering: pixelated`; Label type, 8px 18px padding; raised bevel.
- **Hover:** surface turns Dusk Stone with a blue-tinted noise tile, border goes light (#f2f2f2), label turns Signal Yellow.
- **Pressed / current:** Pressed Stone with a darker noise tile, sunken bevel, contents nudge down 1px. `aria-pressed="true"` uses the same look so the current mood stays pressed in.
- **Focus:** 3px Signal Yellow outline, 2px offset.
- **Disabled:** flat Dead Stone, no noise, grey label (#a2a2a2), no label shadow, faces greyscaled.

### Mood Buttons
The four mood stone buttons in the Settings panel's Claude's mood section, in a 2x2 grid (52px tall, 6px 12px padding), each led by that mood's critter face (36x24). The pressed one shows a 3px underline in its own mood hue inside the bevel.

### Cards / Containers (HUD panel)
- **Corner Style:** square (0px).
- **Background:** HUD Navy.
- **Shadow Strategy:** HUD lift (see Elevation & Depth).
- **Border:** 3px HUD Edge, plus the 2px inner HUD Rim. The mood panel adds an 8px top band in the current mood hue, which eases between hues over 300ms.
- **Internal Padding:** 16px 18px (12px 14px under 720px).
- **Slap:** when the mood changes, the mood panel lifts, tilts 1.5deg and settles back in 420ms on the ease-out curve.

### Inputs / Fields
- **Style:** Field Black, 2px Field Edge border, square, 40px tall, LCD Input type in #e8e8e8, Signal Yellow caret. Each row reads face, label, input, counter (`n/16`).
- **Focus:** border goes white; no glow.
- **Error:** border Error Pink, message in Error Text caption under the input.

### LCD Preview (signature)
A 16-cell character LCD: LCD Bezel frame (8px padding, 2px near-black border), LCD Glass face with 6px padding, 16 equal cells with 2px gaps, each cell a faint white wash holding one VT323 glyph in LCD Ink. It mirrors the editor live while typing. Offline, the glass dims to #5d6b3a.

### Time-in-Mood Bar (signature)
Twenty 8x6px steps with 2px gaps; lit steps take the mood hue, unlit ones are 12% white. Steps fill on a log scale up to 10 minutes.

### Stats Panel

Screen Time's information design in the HUD's own material. A navy side panel like Settings, opened by the Stats stone button. Week and Today are two stone buttons; the active one is pressed. Each view asks one question ("how long did Claude wait on you?"): a caption, one big number in VT323 at 56px (the LCD face, whose digits stay legible where the pixel font's 5 reads as S), and one comparison with a stepped pixel arrow (Mint when the wait went down, Alarm Red when it went up). Week view: square bars in a dark inset well like the LCD, earlier days in stats-bar-soft, today in Claude orange, with a Signal Yellow pixel-dashed average line. Today view: the same well and bars, one bar per hour showing the minutes Claude waited on you, all in Claude orange, with nag time stacked on top in Alarm Red and a two-item legend. Then at most four list rows separated by rim lines, each led by a critter face, with the value in soft ink. In Week view every row is a daily average, matching the headline, so nothing needs converting. A small "Sample" tag marks sample numbers.

### Seen Flag
A small uppercase "New" chip in the mood hue with Ink on Hue text, blinking in two hard steps, shown on DONE and NEEDS_YOU until the page has been looked at.

### Critter and Scene (signature)
The 18x12-cell critter sprite is drawn from code at an integer pixel unit, with a one-pixel cream rim. Mood is behaviour: IDLE wanders and naps (sleep emote), WORKING paces fast with thinking dots in a white bubble, DONE runs to centre and jumps, NEEDS_YOU runs to the front with a red "!" bubble. Clouds drift; all motion stops under `prefers-reduced-motion`.

## Do's and Don'ts

### Do:
- **Do** draw any new scenery on the same low-res canvas, with Bayer dithering for gradients and no image smoothing.
- **Do** show every mood with the critter's face plus its name; use the mood hue only for the current mood.
- **Do** build every control as a stone button: noise tile, 2px Stone Edge, raised bevel, blue-tinted hover, sunken pressed state.
- **Do** put new panels on HUD Navy with the 3px edge, 2px inner rim and the soft HUD lift.
- **Do** keep every corner square (0px).
- **Do** use Signal Yellow (#ffffa0) as the single interaction highlight: hover labels, focus outlines, carets.
- **Do** honour `prefers-reduced-motion` by stopping all animation and transitions.

### Don't:
- **Don't** use the real Bliss photograph, Minecraft textures, sprites or fonts, or OS window chrome (title bars, close boxes). The world is generated, not borrowed.
- **Don't** round corners or soften pixel edges.
- **Don't** use clay orange for UI; it belongs to the critter.
- **Don't** let colour alone tell moods apart.
- **Don't** give panels a hard offset block shadow; hard depth lives inside the stone bevel.
- **Don't** set any non-LCD text in VT323, or any LCD text in Pixelify Sans.
- **Don't** let the page scroll; long content scrolls inside its panel.
