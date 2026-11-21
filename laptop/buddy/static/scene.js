// The hill: a low-resolution pixel landscape scaled up crisp, with drifting
// clouds and the critter walking along the hilltop. Its behaviour is the mood.
(function () {
  "use strict";

  const canvas = document.getElementById("scene");
  const ctx = canvas.getContext("2d");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let W = 320;
  let H = 180;
  let U = 2; // scene pixels per critter pixel
  let sky = null;
  let land = null;
  let clouds = [];
  const spr = document.createElement("canvas"); // critter layer
  const rim = document.createElement("canvas"); // its sticker outline

  // ---------- deterministic noise so the hill doesn't shimmer on resize ----------
  function hash(x, y) {
    let h = (x * 374761393 + y * 668265263) | 0;
    h = (h ^ (h >>> 13)) * 1274126177;
    return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
  }
  function seeded(seed) {
    let s = seed >>> 0;
    return function () {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
  function dither(x, y) { return (BAYER[(y & 3) * 4 + (x & 3)] + 0.5) / 16; }

  function rgb(hex) { const n = parseInt(hex.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  const SKY = ["#1b4fc9", "#2463d6", "#2f78e0", "#4590ea", "#62a7f0", "#86bdf4", "#a9d1f7"].map(rgb);
  const GRASS = ["#1f5e17", "#2b7a1c", "#3a9420", "#4fab25", "#69c22c", "#86d43a", "#a6e34d"].map(rgb);
  const FIELD = ["#1d5a16", "#27711b", "#348a1f", "#45a024", "#5bb52a"].map(rgb);
  const FAR = rgb("#7f9fc6");
  const FAR_SHADE = rgb("#6d8db6");

  // ---------- time of day, from the real local clock ----------
  // shortcut: fixed hours year-round (no seasons or location), good enough for a desk toy.
  const SKIES = {
    day: SKY,
    sunset: ["#2b2c6e", "#4a3b8f", "#7a4b9c", "#b45e93", "#e47a7c", "#f6a06a", "#ffc77a"].map(rgb),
    night: ["#040a1e", "#071129", "#0a1834", "#0e1f3f", "#13284b", "#193156", "#203a5f"].map(rgb),
  };
  // How each look tints the land and clouds (multiplies their colours).
  const TINTS = { day: [1, 1, 1], sunset: [1, 0.8, 0.72], night: [0.26, 0.4, 0.55] };
  // [hour, look]: blend between neighbours, so 18:00 to 19:00 fades day into sunset.
  const KEYS = [[0, "night"], [5, "night"], [6, "sunset"], [7, "day"], [18, "day"], [19, "sunset"], [20, "night"], [24, "night"]];
  let light = null;    // the blended look the background was last painted with
  let lightStep = -1;  // which 5-minute slot that was, so we repaint only when it changes

  function clockHour() { const d = new Date(); return d.getHours() + d.getMinutes() / 60; }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function tinted(c, tint) { return [Math.round(c[0] * tint[0]), Math.round(c[1] * tint[1]), Math.round(c[2] * tint[2])]; }
  function lightAt(hour) {
    let k = 0;
    while (hour >= KEYS[k + 1][0]) k++;
    const a = KEYS[k];
    const b = KEYS[k + 1];
    const t = (hour - a[0]) / (b[0] - a[0]);
    const sky = SKIES[a[1]].map(function (c, i) { return mix(c, SKIES[b[1]][i], t).map(Math.round); });
    const night = (a[1] === "night" ? 1 - t : 0) + (b[1] === "night" ? t : 0);
    return { sky: sky, tint: mix(TINTS[a[1]], TINTS[b[1]], t), night: night };
  }

  // ---------- geometry ----------
  // portrait screens push the land down so the info panel doesn't cover the hilltop
  function drop() { return W < H ? H * 0.1 : 0; }
  function horizonY() { return Math.round(H * 0.63 + drop()); }
  function hillY(x) {
    const bump = Math.exp(-Math.pow((x - crestX()) / (0.36 * Math.max(W, H * 1.4)), 2));
    return H * (0.645 - 0.235 * bump) + drop() + Math.sin(x * 0.045) * 0.8;
  }
  function fieldY(x) { return H * 0.86 + drop() * 0.5 + Math.sin(x / 23) * 1.2 + Math.sin(x / 7.3) * 0.5; }
  function crestX() { return W < H ? W * 0.5 : W * 0.34; }
  // where it performs: just right of the info panel on wide screens
  function stageX() { return W * 0.5; }

  function paintBackground() {
    const tint = light.tint;
    const grass = GRASS.map(function (c) { return tinted(c, tint); });
    const field = FIELD.map(function (c) { return tinted(c, tint); });
    const far = tinted(FAR, tint);
    const farShade = tinted(FAR_SHADE, tint);
    const img = ctx.createImageData(W, H);
    const d = img.data;
    const skyImg = ctx.createImageData(W, H);
    const sd = skyImg.data;
    const hz = horizonY();
    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        const i = (y * W + x) * 4;
        const top = hillY(x);
        const fy = fieldY(x);
        let c;
        if (y >= fy) {
          // foreground field: darker, streaky, with a few flowers
          const t = Math.min(1, (y - fy) / (H - fy + 1));
          const n = hash(x >> 1, y) * 0.35;
          const v = (1 - t) * 0.55 + 0.25 + n - 0.15;
          c = band(field, v, x, y);
          if (hash(x, y * 7) > 0.994 && y > fy + 2) c = tinted(hash(y, x) > 0.5 ? [255, 236, 102] : [255, 255, 240], tint);
        } else if (y >= top) {
          // the hill: lit from the upper left, so slopes facing left glow
          const slope = (hillY(x + 1) - hillY(x - 1)) / 2;
          const depth = (y - top) / (fy - top + 1);
          let v = 0.62 - slope * 0.9 - depth * 0.38 + (hash(x, y) - 0.5) * 0.16;
          if (y - top < 1.5) v += 0.18; // sunlit rim
          c = band(grass, v, x, y);
        } else {
          const farTop = hz - 7 * Math.max(0, Math.sin((x / W - 0.62) * 9)) - 3 * Math.max(0, Math.sin(x / 11));
          if (x > W * 0.62 && y >= farTop && y < hz + 2) {
            c = hash(x, y) > 0.7 || y > farTop + 3 ? farShade : far;
          } else {
            c = band(light.sky, Math.min(1, y / hz), x, y);
            // stars fade in with the night, thinning toward the horizon
            if (light.night > 0 && hash(x * 3, y * 5) > 1 - 0.008 * light.night * (1 - y / hz)) {
              c = hash(x, y * 3) > 0.6 ? [235, 240, 255] : [150, 165, 210];
            }
            sd[i] = c[0]; sd[i + 1] = c[1]; sd[i + 2] = c[2]; sd[i + 3] = 255;
            continue; // sky stays transparent on the land layer
          }
        }
        d[i] = c[0]; d[i + 1] = c[1]; d[i + 2] = c[2]; d[i + 3] = 255;
      }
    }
    sky = layer(skyImg);
    land = layer(img);
  }
  function layer(imageData) {
    const off = document.createElement("canvas");
    off.width = W; off.height = H;
    off.getContext("2d").putImageData(imageData, 0, 0);
    return off;
  }

  // ordered-dither between palette steps, like an old 16-colour wallpaper
  function band(pal, v, x, y) {
    v = Math.max(0, Math.min(0.999, v)) * (pal.length - 1);
    const lo = Math.floor(v);
    return v - lo > dither(x, y) ? pal[Math.min(lo + 1, pal.length - 1)] : pal[lo];
  }

  // ---------- clouds ----------
  function makeCloud(rand, size, tint) {
    const w = Math.round(size * (1.8 + rand()));
    const h = Math.round(size * 0.9);
    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d");
    const puffs = [];
    const n = 4 + Math.floor(rand() * 3);
    const base = size * 0.2;
    for (let k = 0; k < n; k++) {
      const fx = (k + 0.5) / n;
      const r = size * (0.2 + 0.24 * Math.sin(fx * Math.PI) + rand() * 0.08);
      puffs.push([w * (0.12 + fx * 0.76), h - base - r * 0.55, r]);
    }
    for (let k = 0; k < 4; k++) puffs.push([w * (0.15 + k * 0.23), h - base, base]);
    const data = g.createImageData(w, h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        let inside = false;
        for (const p of puffs) if ((x - p[0]) ** 2 + (y - p[1]) ** 2 <= p[2] * p[2]) { inside = true; break; }
        if (!inside || y > h - 2) continue;
        const i = (y * w + x) * 4;
        const under = y / h > 0.62 + dither(x, y) * 0.18;
        const col = tinted(under ? [214, 228, 246] : [255, 255, 255], tint);
        data.data[i] = col[0]; data.data[i + 1] = col[1]; data.data[i + 2] = col[2]; data.data[i + 3] = 255;
      }
    }
    g.putImageData(data, 0, 0);
    return c;
  }
  function makeClouds(old) {
    const rand = seeded(7);
    const list = [];
    const count = Math.max(3, Math.round(W / 60));
    for (let k = 0; k < count; k++) {
      const size = 10 + rand() * 14;
      const x = (k / count) * W + rand() * 30;
      list.push({ img: makeCloud(rand, size, light.tint), x: old ? old[k].x : x, y: 4 + rand() * (H * 0.4), speed: 1.2 + rand() * 2.2 });
    }
    return list;
  }

  // Repaint the sky, land and clouds when the clock enters a new 5-minute slot.
  function updateLight(force) {
    const hour = clockHour();
    const step = Math.floor(hour * 12);
    if (!force && step === lightStep) return;
    lightStep = step;
    light = lightAt(hour);
    paintBackground();
    clouds = makeClouds(force ? null : clouds);
  }

  // ---------- sun and moon, on one arc across the sky ----------
  function disk(cx, cy, r, color) {
    ctx.fillStyle = color;
    for (let dy = -r; dy <= r; dy++) {
      const w = Math.round(Math.sqrt(r * r - dy * dy));
      ctx.fillRect(Math.round(cx - w), Math.round(cy + dy), 2 * w + 1, 1);
    }
  }
  // A clean pixel crescent, built once: moon pixels outside a shadow circle, measured
  // from pixel centres so both curves are smooth, then stray single pixels trimmed.
  let moonCache = null;
  function moonSprite() {
    if (moonCache) return moonCache;
    const n = 21;
    const lit = {};
    function key(x, y) { return x + "," + y; }
    for (let y = 0; y < n; y++) {
      for (let x = 0; x < n; x++) {
        const px = x + 0.5 - n / 2;
        const py = y + 0.5 - n / 2;
        const inMoon = px * px + py * py <= 10.5 * 10.5;
        const inShadow = (px - 5) * (px - 5) + py * py <= 9.5 * 9.5;
        if (inMoon && !inShadow) lit[key(x, y)] = true;
      }
    }
    let changed = true;
    while (changed) {
      changed = false;
      Object.keys(lit).forEach(function (k) {
        const xy = k.split(",").map(Number);
        let nb = 0;
        [[1, 0], [-1, 0], [0, 1], [0, -1]].forEach(function (d) { if (lit[key(xy[0] + d[0], xy[1] + d[1])]) nb++; });
        if (nb < 2) { delete lit[k]; changed = true; }
      });
    }
    moonCache = document.createElement("canvas");
    moonCache.width = moonCache.height = n;
    const g = moonCache.getContext("2d");
    g.fillStyle = "#f4f1e4";
    Object.keys(lit).forEach(function (k) { const xy = k.split(","); g.fillRect(+xy[0], +xy[1], 1, 1); });
    // three small craters in the thick middle of the crescent
    g.fillStyle = "#d8d2c0";
    g.fillRect(2, 8, 2, 1);
    g.fillRect(1, 12, 1, 1);
    g.fillRect(3, 11, 1, 2);
    return moonCache;
  }

  function drawSunAndMoon() {
    const hour = clockHour();
    const hz = horizonY();
    // t runs 0 to 1 across the body's time in the sky; below the horizon the land hides it
    // kept right of the info panel and high, so it rarely hides behind Claude
    function arc(t) { return { x: W * (0.32 + 0.64 * t), y: hz + 6 - Math.sin(Math.PI * t) * H * 0.58 }; }
    if (hour >= 5.5 && hour <= 19.8) {
      const t = (hour - 5.5) / 14.3;
      const p = arc(t);
      const low = 1 - Math.min(1, Math.sin(Math.PI * t) * 1.6); // 1 near the horizon
      disk(p.x, p.y, 13, "rgba(255,240,170,0.3)");
      disk(p.x, p.y, 9, low > 0.5 ? "#ff9a4d" : "#fff1a8");
    }
    if (hour >= 19.5 || hour <= 6) {
      const p = arc(((hour - 19.5 + 24) % 24) / 10.5);
      disk(p.x, p.y, 15, "rgba(244,241,228,0.06)");
      ctx.drawImage(moonSprite(), Math.round(p.x) - 10, Math.round(p.y) - 10);
    }
  }

  // ---------- the critter's brain ----------
  const bud = {
    x: 0, dir: 1, target: 0, pauseUntil: 0, walked: 0, hop: 0, hopV: 0,
    mood: "IDLE", moodSince: 0, offline: false, blinkAt: -1, nextBlink: 2, popAt: -10,
  };

  function setMood(mood, changed, secondsIn) {
    const now = performance.now() / 1000;
    if (changed || mood !== bud.mood) {
      bud.mood = mood;
      bud.moodSince = now - (secondsIn || 0);
      bud.pauseUntil = 0;
      bud.target = pickTarget();
      if (changed) { bud.popAt = now; kick(5); }
    }
  }
  function setOffline(v) { bud.offline = v; }

  function kick(v) { if (bud.hop === 0 && !reduceMotion.matches) bud.hopV = v * 9; }

  function pickTarget() {
    const lo = W > 1.2 * H ? W * 0.32 : W * 0.12; // keep clear of the info panel
    const hi = W * 0.88;
    const c = stageX();
    switch (bud.mood) {
      case "WORKING": return bud.x < c ? c + W * 0.1 : c - W * 0.1;
      case "DONE":
      case "NEEDS_YOU":
      case "ANNOYED":
      case "YELLING": return c;
      default: return Math.max(lo, Math.min(hi, bud.x + (Math.random() - 0.5) * W * 0.5));
    }
  }

  function update(dt, now) {
    const still = reduceMotion.matches;
    const inMood = now - bud.moodSince;
    const sleepy = bud.offline || (bud.mood === "IDLE" && inMood > 30);
    let speed = 0;
    if (!still && !sleepy) {
      speed = { IDLE: 9, WORKING: 30, DONE: 42, NEEDS_YOU: 48, ANNOYED: 48, YELLING: 60 }[bud.mood] || 9;
    }
    const dx = bud.target - bud.x;
    if (now >= bud.pauseUntil && Math.abs(dx) > 0.6 && speed > 0) {
      bud.dir = dx > 0 ? 1 : -1;
      const step = Math.min(Math.abs(dx), speed * dt);
      bud.x += bud.dir * step;
      bud.walked += step;
    } else if (Math.abs(dx) <= 0.6 && now >= bud.pauseUntil) {
      // arrived: decide what's next
      if (bud.mood === "IDLE") { bud.pauseUntil = now + 2 + Math.random() * 4; bud.target = pickTarget(); }
      else if (bud.mood === "WORKING") { bud.pauseUntil = now + 0.3; bud.target = pickTarget(); }
      else if (bud.mood === "DONE" && !still) { kick(6); bud.pauseUntil = now + 0.9; }
      else if (bud.mood === "YELLING" && !still) { kick(8); bud.pauseUntil = now + 0.5; }
    }

    // hop physics, in scene pixels
    if (bud.hopV !== 0 || bud.hop > 0) {
      bud.hop += bud.hopV * dt;
      bud.hopV -= 260 * dt;
      if (bud.hop <= 0) { bud.hop = 0; bud.hopV = 0; }
    }
    return sleepy;
  }

  function render(now, sleepy) {
    ctx.drawImage(sky, 0, 0);
    drawSunAndMoon();
    for (const c of clouds) ctx.drawImage(c.img, Math.round(c.x), Math.round(c.y));
    ctx.drawImage(land, 0, 0);

    const moving = Math.abs(bud.target - bud.x) > 0.6 && now >= bud.pauseUntil && !sleepy && !reduceMotion.matches;
    const legs = sleepy ? -1 : moving ? (Math.floor(bud.walked / 2.5) % 2) + 1 : 0;
    const face = faceFor(now, sleepy);
    let arms = "down";
    if ((bud.mood === "NEEDS_YOU" || bud.mood === "YELLING") && !bud.offline) arms = reduceMotion.matches ? "up" : (Math.floor(now * 5) % 2 ? "waveL" : "waveR");
    if (bud.mood === "DONE" && bud.hop > 2) arms = "up";

    const sw = Critter.W * U;
    const sh = Critter.H * U;
    const sitting = legs === -1;
    const LEG_COLS = [3, 5, 12, 14];
    const left = Math.round(bud.x - sw / 2);
    // first painted grass row under x (the land layer fills from y >= hillY)
    function grassRow(x) { return Math.ceil(hillY(x)); }
    // seat on the lowest ground under any foot so the bottom row overlaps the grass;
    // uphill feet just sink into it
    const grounds = LEG_COLS.map(function (c) { return grassRow(left + (c + 0.5) * U); });
    const feet = (sitting ? grassRow(bud.x) : Math.max.apply(null, grounds)) + 1;
    const bob = moving && bud.mood !== "IDLE" ? (Math.floor(bud.walked / 2.5) % 2) : 0;
    const top = Math.round(feet - sh - bud.hop - bob);
    const facingFront = bud.mood !== "IDLE" && bud.mood !== "WORKING";

    // contact shadow, following the slope column by column
    const shw = Math.max(4, Math.round(sw * 0.8 - bud.hop));
    ctx.fillStyle = "rgba(20,60,10,0.35)";
    for (let x = Math.round(bud.x - shw / 2); x < Math.round(bud.x + shw / 2); x++) {
      ctx.fillRect(x, grassRow(x), 1, Math.max(1, U - 1));
    }

    // draw the critter on its own layer so it can get a die-cut sticker rim
    spr.width = sw + 2;
    spr.height = sh + 2;
    const sctx = spr.getContext("2d");
    sctx.imageSmoothingEnabled = false;
    Critter.draw(sctx, 1, 1, U, {
      face: face,
      look: facingFront && !moving ? 0 : bud.dir,
      legs: legs,
      arms: arms,
      grey: bud.offline,
    });
    rim.width = spr.width;
    rim.height = spr.height;
    const rctx = rim.getContext("2d");
    rctx.drawImage(spr, 0, 0);
    rctx.globalCompositeOperation = "source-in";
    rctx.fillStyle = "#fff8ee";
    rctx.fillRect(0, 0, rim.width, rim.height);
    [[-1, 0], [1, 0], [0, -1], [0, 1]].forEach(function (d) { ctx.drawImage(rim, left - 1 + d[0], top - 1 + d[1]); });
    ctx.drawImage(spr, left - 1, top - 1);
    drawEmote(now, left + sw / 2, top, sleepy);
  }

  function faceFor(now, sleepy) {
    if (sleepy) return "sleep";
    const base = Critter.MOODS[bud.mood].face;
    if (base === "open" || base === "focus") {
      if (now >= bud.nextBlink) { bud.blinkAt = now; bud.nextBlink = now + 2 + Math.random() * 4; }
      if (now < bud.blinkAt + 0.14) return "blink";
    }
    return base;
  }

  // ---------- emotes above the head ----------
  function rect(c, x, y, w, h) { ctx.fillStyle = c; ctx.fillRect(Math.round(x), Math.round(y), w, h); }
  function bubble(cx, top, w, h) {
    const x = Math.round(cx - w / 2);
    rect("#1c1f33", x - 1, top, w + 2, h);
    rect("#1c1f33", x, top - 1, w, h + 2);
    rect("#ffffff", x, top, w, h);
    rect("#1c1f33", Math.round(cx) - 1, top + h + 1, 2, 1);
    rect("#ffffff", Math.round(cx) - 1, top + h, 2, 1);
    return x;
  }
  function drawEmote(now, cx, headTop, sleepy) {
    const p = Math.max(1, Math.round(U / 2)); // emote pixel size
    const pop = Math.min(1, (now - bud.popAt) / 0.18);
    const lift = reduceMotion.matches ? 0 : Math.round((1 - pop) * 3);
    if (sleepy) {
      // three Zs drifting up
      for (let k = 0; k < 3; k++) {
        const t = reduceMotion.matches ? k / 3 : ((now * 0.5 + k / 3) % 1);
        const zx = cx + 6 * p + t * 8 * p + k * p;
        const zy = headTop - 3 * p - t * 12 * p;
        const s = p * (k === 2 ? 2 : 1);
        rect("#ffffff", zx, zy, 3 * s, s); rect("#ffffff", zx + s, zy + s, s, s); rect("#ffffff", zx, zy + 2 * s, 3 * s, s);
      }
      return;
    }
    if (bud.mood === "WORKING") {
      const top = headTop - 10 * p - lift;
      bubble(cx, top, 13 * p, 6 * p);
      const n = reduceMotion.matches ? 3 : (Math.floor(now * 3) % 3) + 1;
      for (let k = 0; k < n; k++) rect("#1c1f33", cx - 5 * p + k * 4 * p, top + 2 * p, 2 * p, 2 * p);
    } else if (bud.mood === "NEEDS_YOU" || bud.mood === "ANNOYED" || bud.mood === "YELLING") {
      const bobY = reduceMotion.matches ? 0 : Math.round(Math.sin(now * 8) * p);
      const top = headTop - 13 * p - lift + bobY;
      bubble(cx, top, 6 * p, 10 * p);
      rect("#e0245e", cx - p, top + 2 * p, 2 * p, 4 * p);
      rect("#e0245e", cx - p, top + 7 * p, 2 * p, 2 * p);
    } else if (bud.mood === "DONE") {
      // twinkling sparkles around the head
      const spots = [[-12, -2], [11, -5], [-7, -9], [6, -11]];
      spots.forEach(function (s, k) {
        const on = reduceMotion.matches || (Math.floor(now * 4 + k * 1.7) % 3) !== 0;
        if (!on) return;
        const x = cx + s[0] * p;
        const y = headTop + s[1] * p - lift;
        const col = k % 2 ? "#fff6a8" : "#ffffff";
        rect(col, x, y - p, p, 3 * p);
        rect(col, x - p, y, 3 * p, p);
      });
    }
  }

  // ---------- loop & sizing ----------
  function resize() {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    H = Math.max(150, Math.min(220, Math.round(vh / 4.6)));
    W = Math.max(60, Math.round(H * vw / vh));
    U = W >= 250 ? 3 : 2; // the critter stays big enough to read from across the room
    canvas.width = W;
    canvas.height = H;
    ctx.imageSmoothingEnabled = false;
    updateLight(true);
    if (!bud.x) bud.x = stageX() - W * 0.06;
    bud.x = Math.max(W * 0.1, Math.min(W * 0.9, bud.x));
    bud.target = pickTarget();
  }

  let last = performance.now();
  function frame(t) {
    const now = t / 1000;
    const dt = Math.min(0.1, (t - last) / 1000);
    last = t;
    if (!reduceMotion.matches) {
      for (const c of clouds) c.x = ((c.x + c.speed * dt + c.img.width) % (W + c.img.width)) - c.img.width;
    }
    updateLight(false);
    const sleepy = update(dt, now);
    render(now, sleepy);
    requestAnimationFrame(frame);
  }

  let resizeTimer = 0;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resize, 120);
  });
  resize();
  requestAnimationFrame(frame);

  window.Scene = { setMood: setMood, setOffline: setOffline };
})();
