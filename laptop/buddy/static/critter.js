// The pixel critter: one 18 x 12 grid, drawn with fillRect so it stays crisp
// at any scale. Shared by the hill scene, the mood buttons and the favicon.
(function () {
  "use strict";

  const W = 18;
  const H = 12;
  const C = {
    body: "#d97757",
    shade: "#b45a3c",
    light: "#ee9b7a",
    ink: "#2a1712",
    shine: "#ffffff",
  };

  const MOODS = {
    IDLE: { label: "Idle", face: "open", blurb: "Just hanging out" },
    WORKING: { label: "Working", face: "focus", blurb: "Claude is thinking" },
    DONE: { label: "Done", face: "happy", blurb: "Claude finished. Look up!" },
    NEEDS_YOU: { label: "Needs you", face: "surprised", blurb: "Claude is waiting on you" },
    // Set only by the nag timer when you ignore DONE or NEEDS_YOU.
    ANNOYED: { label: "Annoyed", face: "annoyed", blurb: "Claude finished a while ago" },
    YELLING: { label: "Yelling", face: "yelling", blurb: "Look at the screen!" },
  };

  // opts: face, look (-1|0|1), legs (0 stand, 1/2 walk frames, -1 sitting),
  // arms ("down" | "up" | "waveL" | "waveR"), grey
  function draw(ctx, ox, oy, u, opts) {
    const o = Object.assign({ face: "open", look: 0, legs: 0, arms: "down", grey: false }, opts);
    const sit = o.legs === -1;
    const dy = sit ? 3 : 0;

    function px(color, x, y, w, h) {
      ctx.fillStyle = o.grey ? greyOf(color) : color;
      ctx.fillRect(Math.round(ox + x * u), Math.round(oy + (y + dy) * u), (w || 1) * u, (h || 1) * u);
    }

    // legs first so the body overlaps their tops
    if (!sit) {
      const legX = [3, 5, 12, 14];
      legX.forEach(function (x, i) {
        let h = 3;
        if (o.legs === 1 && (i === 1 || i === 3)) h = 2;
        if (o.legs === 2 && (i === 0 || i === 2)) h = 2;
        px(C.shade, x, 9, 1, h);
      });
    }

    // body
    px(C.body, 2, 0, 14, 9);
    px(C.light, 3, 0, 11, 1);
    px(C.light, 2, 1, 1, 3);
    px(C.shade, 2, 8, 14, 1);
    px(C.shade, 15, 1, 1, 7);

    // arms
    const armUpL = o.arms === "up" || o.arms === "waveL";
    const armUpR = o.arms === "up" || o.arms === "waveR";
    if (armUpL) { px(C.body, 0, 1, 2, 3); px(C.light, 0, 1, 1, 1); }
    else { px(C.body, 0, 4, 2, 2); px(C.shade, 0, 5, 2, 1); }
    if (armUpR) { px(C.body, 16, 1, 2, 3); }
    else { px(C.body, 16, 4, 2, 2); px(C.shade, 16, 5, 2, 1); }

    // face; `look` slides the eyes toward where it's going
    const l = o.look;
    switch (o.face) {
      case "blink":
      case "sleep":
        // closed eyes
        px(C.ink, 5 + l, 4, 2, 1);
        px(C.ink, 11 + l, 4, 2, 1);
        break;
      case "focus":
        // a little narrower: concentrating
        px(C.ink, 5 + l, 3, 2, 2);
        px(C.ink, 11 + l, 3, 2, 2);
        break;
      case "happy":
        // ^ ^ eyes
        px(C.ink, 5 + l, 2, 2, 1); px(C.ink, 4 + l, 3, 1, 1); px(C.ink, 7 + l, 3, 1, 1);
        px(C.ink, 11 + l, 2, 2, 1); px(C.ink, 10 + l, 3, 1, 1); px(C.ink, 13 + l, 3, 1, 1);
        break;
      case "surprised":
        // a touch taller, with a glint
        px(C.ink, 5 + l, 1, 2, 4); px(C.shine, 5 + l, 1, 1, 1);
        px(C.ink, 11 + l, 1, 2, 4); px(C.shine, 11 + l, 1, 1, 1);
        break;
      case "annoyed":
        // heavy lids over narrowed eyes
        px(C.shade, 4 + l, 2, 3, 1); px(C.ink, 5 + l, 3, 2, 2);
        px(C.shade, 11 + l, 2, 3, 1); px(C.ink, 11 + l, 3, 2, 2);
        break;
      case "yelling":
        // > < eyes, the mascot's own eyes from the LCD face
        [[4, 1], [5, 2], [6, 3], [5, 4], [4, 5]].forEach(function (p) { px(C.ink, p[0] + l, p[1]); });
        [[13, 1], [12, 2], [11, 3], [12, 4], [13, 5]].forEach(function (p) { px(C.ink, p[0] + l, p[1]); });
        break;
      default: // open
        px(C.ink, 5 + l, 2, 2, 3);
        px(C.ink, 11 + l, 2, 2, 3);
    }
  }

  const greyCache = {};
  function greyOf(hex) {
    if (greyCache[hex]) return greyCache[hex];
    const n = parseInt(hex.slice(1), 16);
    const g = Math.round(((n >> 16) & 255) * 0.3 + ((n >> 8) & 255) * 0.59 + (n & 255) * 0.11);
    const v = Math.round(g * 0.85 + 30);
    return (greyCache[hex] = "rgb(" + v + "," + v + "," + (v + 8) + ")");
  }

  // A standing critter wearing a mood's face, for icons.
  function drawIcon(canvas, mood, grey) {
    const ctx = canvas.getContext("2d");
    const u = Math.floor(Math.min(canvas.width / W, canvas.height / H));
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const m = MOODS[mood] || MOODS.IDLE;
    draw(ctx, Math.floor((canvas.width - W * u) / 2), Math.floor((canvas.height - H * u) / 2), u, {
      face: mood === "IDLE" ? "open" : m.face,
      arms: mood === "NEEDS_YOU" ? "up" : "down",
      grey: !!grey,
    });
  }

  // Recolour the critter from one base colour: a darker shade and a lighter highlight.
  function setColor(hex, lightEyes) {
    const n = parseInt(hex.slice(1), 16);
    const rgb = [(n >> 16) & 255, (n >> 8) & 255, n & 255];
    function css(f) { return "rgb(" + rgb.map(f).join(",") + ")"; }
    C.body = hex;
    C.shade = css(function (v) { return Math.round(v * 0.8); });
    C.light = css(function (v) { return Math.round(v + (255 - v) * 0.3); });
    // Only the black body gets light eyes; every other colour keeps the dark ones.
    C.ink = lightEyes ? "#f5f3ec" : "#2a1712";
    C.shine = lightEyes ? "#2a1712" : "#ffffff";
  }

  window.Critter = { W: W, H: H, MOODS: MOODS, draw: draw, drawIcon: drawIcon, setColor: setColor };
})();
