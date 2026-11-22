// The buddy's face on a phone: orange screen, two black pixel-art eyes.
// Same shapes and animations as the old TFT firmware (face.c), drawn on a
// canvas. Asks the laptop for the buddy's state 4 times per second (/status).
(function () {
  "use strict";

  // ---------- look (same numbers as face.c, in a 320 x 240 design space) ----------
  const DESIGN_W = 320;     // the face is designed for 320 x 240 (the old TFT)
  const DESIGN_H = 240;     // and scaled up to fill the phone
  const BG = "#d97757";     // Claude orange
  const INK = "#000000";    // eye colour
  const EYE_W = 28;         // normal eye width
  const EYE_H = 64;         // normal eye height
  const STROKE = 10;        // line thickness for ^ ^, > <, brows
  const BOX_W = 96;         // each eye sits in a 96 x 128 box...
  const LEFT_CX = BOX_W / 2;              // ...pushed to the left edge
  const RIGHT_CX = DESIGN_W - BOX_W / 2;  // ...and the right edge
  const CY = DESIGN_H / 2;                // eyes centred vertically

  // ---------- timing ----------
  const POLL_MS = 250;            // how often to ask the laptop for the state
  const OFFLINE_AFTER_MS = 2000;  // no answer this long: show closed eyes
  const HAPPY_BOUNCE_MS = 1200;   // ^ ^ bounces this long after Claude finishes
  const OUCH_SHAKE_MS = 900;      // > < shakes this long
  const SLAP_REACT_MS = 1500;     // > < after a slap, then back to the mood

  // Buddy state (from the laptop) -> face. Same mapping as FACE_FOR_STATE
  // in serial_output.py.
  const FACE_FOR_STATE = {
    IDLE: "normal",
    WORKING: "normal",
    DONE: "happy",
    NEEDS_YOU: "sad",
    ANNOYED: "ouch",
    YELLING: "ouch",
  };

  const canvas = document.getElementById("face");
  const ctx = canvas.getContext("2d");

  // ---------- what to show ----------
  let baseFace = "normal";     // from the buddy's state
  let face = "normal";         // on screen right now (may be a slap reaction)
  let faceSince = 0;           // when `face` started (for bounce/shake/droop)
  let reactUntil = 0;          // end of a slap reaction, 0 = none
  let lastAnswer = 0;          // last time the laptop answered
  let lastSlaps = null;        // slap counter from /status, to notice new slaps

  // Blinks and glances (normal and sad faces).
  let nextBlink = 0;
  let blinkStart = -1;
  let lookX = 0;
  let lookTarget = 0;
  let nextGlance = 0;

  function setFace(name, now) {
    if (name !== face) {
      face = name;
      faceSince = now;
    }
  }

  // ---------- talking to the laptop ----------
  async function poll() {
    try {
      // cache: "no-store" so Safari never shows an old answer.
      const res = await fetch("/status", { cache: "no-store" });
      if (res.ok) {
        const status = await res.json();
        const now = performance.now();
        lastAnswer = now;
        baseFace = FACE_FOR_STATE[status.state] || "normal";
        // A new slap: show > < for a moment, like the board used to.
        if (lastSlaps !== null && status.slaps > lastSlaps) {
          reactUntil = now + SLAP_REACT_MS;
          setFace("ouch", now);
          faceSince = now;     // restart the shake even if already "ouch"
        }
        lastSlaps = status.slaps;
      }
    } catch (e) {
      // Laptop unreachable (Wi-Fi, server stopped): the draw loop shows
      // closed eyes after OFFLINE_AFTER_MS.
    }
    setTimeout(poll, POLL_MS);
  }

  // ---------- drawing helpers (design coordinates) ----------
  function rect(x, y, w, h) {
    ctx.fillRect(x, y, w, h);
  }

  function line(x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  // How tall an eye is during a blink: shrinks to 4 and back over 160 ms.
  function blinkHeight(now, fullH) {
    if (blinkStart < 0 && now >= nextBlink) {
      blinkStart = now;
    }
    if (blinkStart >= 0) {
      const t = now - blinkStart;
      if (t > 160) {
        blinkStart = -1;
        nextBlink = now + 2000 + Math.random() * 4000;   // next blink in 2 to 6 s
        return fullH;
      }
      const closed = t < 80 ? t / 80 : (160 - t) / 80;    // 0 -> 1 -> 0
      return Math.max(4, fullH * (1 - closed));
    }
    return fullH;
  }

  // One eye. side 0 = left, 1 = right (mirrors the slanted shapes).
  function drawEye(side, shape, dx, dy, h) {
    const cx = (side === 0 ? LEFT_CX : RIGHT_CX) + dx;
    const cy = CY + dy;
    const m = side === 0 ? 1 : -1;   // +1: the inner side is to the right

    if (shape === "rect") {                       // o o
      rect(cx - EYE_W / 2, cy - h / 2, EYE_W, h);
    } else if (shape === "happy") {               // ^ ^
      line(cx - 22, cy + 10, cx, cy - 14);
      line(cx, cy - 14, cx + 22, cy + 10);
    } else if (shape === "ouch") {                // > <
      line(cx - 14 * m, cy - 24, cx + 14 * m, cy);
      line(cx + 14 * m, cy, cx - 14 * m, cy + 24);
    } else if (shape === "sad") {                 // /. .\
      rect(cx - EYE_W / 2, cy + 14 - h / 2, EYE_W, h);       // eyes sit lower
      line(cx - 20 * m, cy - 26, cx + 18 * m, cy - 42);      // brow, raised inside
    } else if (shape === "closed") {              // - -  (laptop unreachable)
      rect(cx - EYE_W / 2, cy - 3, EYE_W, 6);
    }
  }

  // ---------- one frame ----------
  function frame(now) {
    // Fit the 320 x 240 design into the screen, keeping its shape. The
    // canvas is drawn at the phone's real pixel density so edges stay sharp.
    const dpr = window.devicePixelRatio || 1;
    const w = window.innerWidth;
    const h = window.innerHeight;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const scale = Math.min(w / DESIGN_W, h / DESIGN_H) * dpr;
    const offsetX = (canvas.width - DESIGN_W * scale) / 2;
    const offsetY = (canvas.height - DESIGN_H * scale) / 2;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(scale, 0, 0, scale, offsetX, offsetY);
    ctx.fillStyle = INK;
    ctx.strokeStyle = INK;
    ctx.lineWidth = STROKE;
    ctx.lineCap = "square";   // square ends look pixel-art, like the TFT

    // A slap reaction ends: back to the face for the buddy's state.
    if (reactUntil && now >= reactUntil) {
      reactUntil = 0;
    }
    if (!reactUntil) {
      setFace(baseFace, now);
    }

    const t = now - faceSince;
    if (now - lastAnswer > OFFLINE_AFTER_MS) {
      drawEye(0, "closed", 0, 0, 0);
      drawEye(1, "closed", 0, 0, 0);
    } else if (face === "happy") {
      const dy = t < HAPPY_BOUNCE_MS && Math.floor(t / 150) % 2 === 1 ? -6 : 0;
      drawEye(0, "happy", 0, dy, 0);
      drawEye(1, "happy", 0, dy, 0);
    } else if (face === "sad") {
      const dy = t < 400 ? t / 100 : 4;            // slow droop
      const eyeH = blinkHeight(now, 40);
      drawEye(0, "sad", 0, dy, eyeH);
      drawEye(1, "sad", 0, dy, eyeH);
    } else if (face === "ouch") {
      const dx = t < OUCH_SHAKE_MS ? (Math.floor(t / 50) % 2 === 1 ? 4 : -4) : 0;
      drawEye(0, "ouch", dx, 0, 0);
      drawEye(1, "ouch", dx, 0, 0);
    } else {
      // normal: look around now and then, and blink.
      if (now >= nextGlance) {
        const targets = [0, 0, 0, -10, 10];
        lookTarget = targets[Math.floor(Math.random() * targets.length)];
        nextGlance = now + 1500 + Math.random() * 3500;
      }
      if (lookX < lookTarget) lookX = Math.min(lookTarget, lookX + 1);
      if (lookX > lookTarget) lookX = Math.max(lookTarget, lookX - 1);
      const eyeH = blinkHeight(now, EYE_H);
      drawEye(0, "rect", lookX, 0, eyeH);
      drawEye(1, "rect", lookX, 0, eyeH);
    }

    requestAnimationFrame(frame);
  }

  // Tap to go full screen where the browser allows it (Android Chrome).
  // On iPhone use "Add to Home Screen" instead.
  document.addEventListener("click", function () {
    const el = document.documentElement;
    if (el.requestFullscreen && !document.fullscreenElement) {
      el.requestFullscreen().catch(function () {});
    }
  });

  poll();
  requestAnimationFrame(frame);
})();
