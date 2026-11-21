---
version: 1
slug: "laptop-buddy-static-index-html"
primary_target: "laptop/buddy/static/index.html"
related_targets: []
---

# Mood page (laptop/buddy/static/index.html)

Mode: Operate. Audience: Claude Buddy owners, glancing from across the desk and occasionally poking the mood. Job: see what mood the buddy is in and for how long, set its mood by hand for testing, and edit the 16-char LCD line per mood. Out of scope here (teammate owns it): STM32 device setup and the global hook installer. Never show prompt or reply contents.

## Direction contract

THESIS: The buddy's mood owns the screen as a giant die-cut sticker of the pixel critter; everything else is a small sticker on the same sheet. Refuses the category default of a white settings card list with a status pill.

OWN-WORLD (user-pinned, replaces the rolled sheet ground): a pixel-art desktop-wallpaper landscape, a rolling bright-green hill under a deep blue sky with drifting pixel clouds, drawn on one low-res canvas scaled up crisp. The orange pixel critter walks along the hill crest. User-pinned too: the UI sits on it as dark navy HUD panels, with each mood's hue as a top band and name colour (IDLE periwinkle, WORKING butter yellow, DONE mint, NEEDS_YOU hot pink), and every button is a grey bevelled stone game button with a pixel-noise texture, a blue-tinted hover and a pressed state for the current mood. Pixel type throughout (Pixelify Sans), with VT323 on the 16-cell LCD preview. Never the actual Bliss photo and never OS window chrome.

STORY: You see the critter's face and know the mood instantly; you read how long it has held; you tap a mood sticker to slap a new critter on; you rewrite what its LCD says.

FIRST VIEWPORT: The full-bleed landscape fills the viewport, and the rimmed critter (about a fifth of the width on desktop, at least 40% on a phone) performs at its centre. A mood panel at top-left holds the mood name, the timer with its stepped time-in-mood bar, and the one LCD preview. The only control on the main screen is a stone "Settings" button at top-right. It opens one panel with Claude's mood (the mood buttons) and Screen messages (the editor); the user asked for this, to keep the scene uncluttered. Decided deviations: settings is a top-right panel, not a bottom peel-off sheet, because the page never scrolls (the scene is full-bleed). There is a single LCD preview, in the mood panel, because a second strip under the critter would repeat the same 16 characters.

FORM: Sticker sheet, position 3 of 7 on the ordered list. seed:8a0adba87ab7bd16. Raises: from emission-line rail, moods differ by eyes, arms and behaviour, never hue alone (user-pinned: no mouth); from the vertical feed, one thing owns the viewport; from the gate board, DONE/NEEDS_YOU keep a "new" flag until seen; from the labanotation score, time-in-mood is drawn as a growing bar; from the acetate manual, each mood owns one full-strength hue; from high-density web, no padding inflation in the editor. Signature move: the critter's behaviour on the hill is the mood (IDLE wanders and naps, WORKING paces fast with thinking dots, DONE runs to centre and jumps, NEEDS_YOU runs to the front waving with a "!"), and the mood sticker slaps on with a peel-and-stick on each change.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
