// Talks to the buddy service: polls /status, sets moods, edits LCD lines.
(function () {
  "use strict";

  const MOODS = Critter.MOODS;
  // Moods you can set and edit here; ANNOYED and YELLING come only from the nag timer.
  const ORDER = ["IDLE", "WORKING", "DONE", "NEEDS_YOU"];
  const LCD_WIDTH = 16;
  const POLL_MS = 1000;

  const $ = function (id) { return document.getElementById(id); };
  const el = {
    moodName: $("mood-heading"), moodTime: $("mood-time"), moodFace: $("mood-face"),
    newTag: $("new-tag"), lcd: $("lcd"), lcdCells: $("lcd-cells"), offline: $("offline"),
    moodPanel: document.querySelector(".mood-panel"), moodButtons: $("mood-buttons"),
    toggle: $("settings-toggle"), panel: $("settings-panel"), form: $("messages-form"),
    rows: $("msg-rows"), status: $("form-status"), save: $("save-btn"), reset: $("reset-btn"), close: $("close-btn"),
  };

  function moodOf(state) { return MOODS[state] || MOODS.IDLE; } // unknown states fall back to Idle
  function isOffline() { return document.body.classList.contains("is-offline"); }
  let current = null;       // last /status payload
  let fetchedAt = 0;        // performance.now() when it arrived
  let lastChange = null;    // change_id we've already reacted to
  let unseen = false;
  let previewText = null;   // LCD draft while typing in the editor

  // Every call to the service: JSON in and out; a non-2xx throws with the server's reason.
  async function api(method, path, body) {
    const res = await fetch(path, {
      method: method,
      cache: "no-store",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    }).catch(function () { throw new Error("the buddy service didn't answer"); });
    const data = await res.json().catch(function () { return null; });
    if (!res.ok) throw new Error(data && typeof data.detail === "string" ? data.detail : "HTTP " + res.status);
    return data;
  }

  const icons = []; // every small face on the page, so a colour change can redraw them
  function faceIcon(mood) {
    const c = document.createElement("canvas");
    icons.push({ canvas: c, mood: mood });
    c.width = 18; c.height = 12;
    c.className = "face";
    c.setAttribute("aria-hidden", "true");
    Critter.drawIcon(c, mood);
    return c;
  }

  // ---------- Claude's colour: 7 presets, the 8th square opens a pixel colour wheel ----------
  const LICORICE = "#2e2b33"; // the black option, the only one with light eyes
  const COLORS = [
    ["Claude orange", "#d97757"], ["Strawberry", "#e05a6d"], ["Banana", "#f2c94c"], ["Mint", "#5cc8b8"],
    ["Blueberry", "#6b8fe6"], ["Licorice", LICORICE], ["Marshmallow", "#efe7dc"],
  ];
  const more = $("color-more");
  const wheelBox = $("wheel-box");
  const presetBtns = [];
  COLORS.forEach(function (pair) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "swatch";
    b.style.background = pair[1];
    b.title = pair[0];
    b.setAttribute("aria-label", pair[0]);
    b.addEventListener("click", function () { setColor(pair[1]); showWheel(false); });
    $("swatches").insertBefore(b, more);
    presetBtns.push({ btn: b, hex: pair[1] });
  });
  // The rainbow square only opens the wheel, so repeat or double clicks can't flicker it shut;
  // picking a preset or closing Settings folds it away.
  function showWheel(open) {
    wheelBox.hidden = !open;
    more.setAttribute("aria-expanded", String(open));
    refreshSwatches();
  }
  // The white frame marks what you chose: the rainbow square while its wheel is open
  // or the colour is a custom one, otherwise the matching preset.
  function refreshSwatches() {
    const hex = Critter.color();
    let isPreset = false;
    presetBtns.forEach(function (p) { if (p.hex === hex) isPreset = true; });
    const customOn = !wheelBox.hidden || !isPreset;
    presetBtns.forEach(function (p) { p.btn.setAttribute("aria-pressed", String(!customOn && p.hex === hex)); });
    more.classList.toggle("is-on", customOn);
    more.style.setProperty("--custom", isPreset ? "transparent" : hex);
  }
  more.addEventListener("click", function () {
    showWheel(true);
    wheel.focus();
  });

  // Hue goes around the wheel, strength from centre (grey) to edge (full colour).
  // Brightness stays at 0.85, which keeps the dark eyes readable; Claude orange sits on it.
  const DEFAULT_COLOR = COLORS[0][1];
  const V = 0.85;
  const wheel = $("wheel");
  const wctx = wheel.getContext("2d");
  const R = (wheel.width - 1) / 2;
  let pick = { h: 0, s: 0 };

  function hsvToHex(h, sat) {
    function f(n) {
      const k = (n + h / 60) % 6;
      return Math.round(255 * (V - V * sat * Math.max(0, Math.min(k, 4 - k, 1))));
    }
    return "#" + [f(5), f(3), f(1)].map(function (v) { return v.toString(16).padStart(2, "0"); }).join("");
  }
  function hexToHs(hex) {
    const n = parseInt(hex.slice(1), 16);
    const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    const max = Math.max(r, g, b), d = max - Math.min(r, g, b);
    let h = 0;
    if (d) h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return { h: (h * 60 + 360) % 360, s: max ? d / max : 0 };
  }

  function drawWheel() {
    const img = wctx.createImageData(wheel.width, wheel.height);
    for (let y = 0; y < wheel.height; y++) {
      for (let x = 0; x < wheel.width; x++) {
        const dx = x - R, dy = y - R, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > R + 0.5) continue;
        const hex = dist > R - 0.5 ? "#0e0e0e" : hsvToHex((Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360, dist / R);
        const n = parseInt(hex.slice(1), 16), i = (y * wheel.width + x) * 4;
        img.data[i] = (n >> 16) & 255; img.data[i + 1] = (n >> 8) & 255; img.data[i + 2] = n & 255; img.data[i + 3] = 255;
      }
    }
    wctx.putImageData(img, 0, 0);
    // marker: a dark ring with a white inside, around the picked spot
    const a = pick.h * Math.PI / 180;
    const mx = Math.round(R + Math.cos(a) * pick.s * (R - 2));
    const my = Math.round(R + Math.sin(a) * pick.s * (R - 2));
    wctx.strokeStyle = "#0e0e0e"; wctx.strokeRect(mx - 2.5, my - 2.5, 5, 5);
    wctx.strokeStyle = "#ffffff"; wctx.strokeRect(mx - 1.5, my - 1.5, 3, 3);
  }

  function wheelPoint(ev) {
    const box = wheel.getBoundingClientRect();
    const dx = (ev.clientX - box.left) / box.width * wheel.width - R - 0.5;
    const dy = (ev.clientY - box.top) / box.height * wheel.height - R - 0.5;
    return { dx: dx, dy: dy, dist: Math.sqrt(dx * dx + dy * dy) };
  }
  // Dragging fires many moves per frame; apply only the latest one, once per frame.
  let pendingPick = null;
  function pickAt(p) {
    pick = { h: (Math.atan2(p.dy, p.dx) * 180 / Math.PI + 360) % 360, s: Math.min(1, p.dist / (R - 1)) };
    if (pendingPick) return;
    pendingPick = requestAnimationFrame(function () {
      pendingPick = null;
      setColor(hsvToHex(pick.h, pick.s), true);
    });
  }
  wheel.addEventListener("pointerdown", function (ev) {
    const p = wheelPoint(ev);
    if (p.dist > R + 0.5) return; // the empty corners around the round wheel do nothing
    ev.preventDefault();
    wheel.focus();
    wheel.setPointerCapture(ev.pointerId);
    pickAt(p);
  });
  // once dragging, leaving the circle just pins the pick to its edge
  wheel.addEventListener("pointermove", function (ev) { if (wheel.hasPointerCapture(ev.pointerId)) pickAt(wheelPoint(ev)); });
  wheel.addEventListener("keydown", function (ev) {
    const step = { ArrowLeft: [-10, 0], ArrowRight: [10, 0], ArrowUp: [0, 0.1], ArrowDown: [0, -0.1] }[ev.key];
    if (!step) return;
    ev.preventDefault();
    pick = { h: (pick.h + step[0] + 360) % 360, s: Math.max(0, Math.min(1, pick.s + step[1])) };
    setColor(hsvToHex(pick.h, pick.s), true);
  });

  function setColor(hex, fromWheel) {
    Critter.setColor(hex, hex === LICORICE);
    try { localStorage.setItem("buddy.color", hex); } catch (e) { /* private mode: just don't remember */ }
    if (!fromWheel) pick = hexToHs(hex);
    drawWheel();
    refreshSwatches();
    wheel.setAttribute("aria-valuenow", String(Math.round(pick.h)));
    wheel.setAttribute("aria-valuetext", "hue " + Math.round(pick.h) + " degrees, strength " + Math.round(pick.s * 100) + " percent");
    icons.forEach(function (i) { Critter.drawIcon(i.canvas, i.mood); });
    const offline = document.body.classList.contains("is-offline");
    Critter.drawIcon(el.moodFace, current && !offline ? current.state : "IDLE", offline);
    if (current) setFavicon(current.state);
  }

  // ---------- stone texture for the blocky buttons ----------
  function stone(base, spread, seed) {
    const c = document.createElement("canvas");
    c.width = c.height = 16;
    const g = c.getContext("2d");
    let s = seed;
    for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) {
      s = (s * 1103515245 + 12345) & 0x7fffffff;
      const k = ((s >> 8) % 5) - 2;
      const v = base.map(function (ch) { return Math.max(0, Math.min(255, ch + k * spread)); });
      g.fillStyle = "rgb(" + v.join(",") + ")";
      g.fillRect(x, y, 1, 1);
    }
    return "url(" + c.toDataURL() + ")";
  }
  const root = document.documentElement.style;
  root.setProperty("--stone", stone([106, 106, 106], 6, 11));
  root.setProperty("--stone-hover", stone([92, 100, 148], 6, 11));
  root.setProperty("--stone-down", stone([79, 79, 83], 5, 23));

  // ---------- time-in-mood bar: 20 pixel steps on a log scale up to 10 minutes ----------
  const BAR_STEPS = 20;
  const timeBar = $("time-bar");
  for (let i = 0; i < BAR_STEPS; i++) timeBar.appendChild(document.createElement("span"));
  function showBar(sec) {
    const lit = Math.min(BAR_STEPS, Math.ceil(BAR_STEPS * Math.log(1 + sec) / Math.log(601)));
    timeBar.childNodes.forEach(function (s, i) { s.classList.toggle("on", i < lit); });
  }

  // ---------- LCD ----------
  for (let i = 0; i < LCD_WIDTH; i++) {
    const cell = document.createElement("span");
    cell.className = "lcd-cell";
    el.lcdCells.appendChild(cell);
  }
  function showLcd(text) {
    const t = (text || "").padEnd(LCD_WIDTH, " ").slice(0, LCD_WIDTH);
    el.lcdCells.childNodes.forEach(function (cell, i) { cell.textContent = t[i] === " " ? " " : t[i]; });
    el.lcd.setAttribute("aria-label", "Buddy's screen shows: " + (text || "nothing"));
  }

  // ---------- mood buttons ----------
  const moodBtns = {};
  ORDER.forEach(function (mood) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "stone-btn mood-btn";
    b.dataset.mood = mood;
    b.setAttribute("aria-pressed", "false");
    const label = document.createElement("span");
    label.textContent = MOODS[mood].label;
    b.append(faceIcon(mood), label);
    b.addEventListener("click", function () { setMood(mood); });
    el.moodButtons.appendChild(b);
    moodBtns[mood] = b;
  });

  // Replies can arrive out of order (a slow poll after a mood click), so only the
  // newest request may change the page.
  let reqSeq = 0;
  let settledSeq = 0;
  async function request(method, path, body) {
    const seq = ++reqSeq;
    try {
      const s = await api(method, path, body);
      if (seq > settledSeq) { settledSeq = seq; apply(s); }
    } catch (err) {
      if (seq > settledSeq) { settledSeq = seq; goOffline(); }
    }
  }

  let moodBusy = false;
  async function setMood(mood) {
    if (moodBusy || isOffline()) return;
    moodBusy = true;
    await request("POST", "/mood", { state: mood });
    moodBusy = false;
  }
  function setMoodButtonsAvailable(on) {
    Object.values(moodBtns).forEach(function (b) { b.setAttribute("aria-disabled", String(!on)); });
  }

  // ---------- status polling ----------
  async function poll() {
    await request("GET", "/status");
    setTimeout(poll, POLL_MS);
  }

  function apply(s) {
    const wasOffline = document.body.classList.contains("is-offline");
    current = s;
    fetchedAt = performance.now();
    document.body.classList.remove("is-offline");
    el.offline.hidden = true;
    Scene.setOffline(false);
    setMoodButtonsAvailable(true);
    // back online with Settings open but the messages never loaded: load them now
    if (wasOffline && !el.panel.hidden && !msgLoaded) loadMessages();

    const first = lastChange === null;
    const changed = !first && s.change_id !== lastChange;
    lastChange = s.change_id;

    if (first || changed || wasOffline) {
      const m = moodOf(s.state);
      document.body.dataset.mood = s.state;
      el.moodName.textContent = m.label;
      Critter.drawIcon(el.moodFace, s.state);
      ORDER.forEach(function (k) { moodBtns[k].setAttribute("aria-pressed", String(k === s.state)); });
      setFavicon(s.state);
      Scene.setMood(s.state, changed, s.seconds_in_state);
      if (changed) {
        el.moodPanel.classList.remove("slap");
        void el.moodPanel.offsetWidth; // restart the animation
        el.moodPanel.classList.add("slap");
      }
      // Claude itself finished or needs you: flag it until you've looked. Only a real
      // change touches the flag, so a reconnect doesn't clear one you haven't seen.
      const wantsYou = s.state !== "IDLE" && s.state !== "WORKING";
      if (changed) setUnseen(s.source !== "manual" && wantsYou);
    }
    if (previewText === null) showLcd(s.text);
    tick();
  }

  function goOffline() {
    if (isOffline()) return; // already showing it; rewriting the live heading would re-announce it
    document.body.classList.add("is-offline");
    el.offline.hidden = false;
    el.moodName.textContent = "Can't find the buddy";
    el.moodTime.textContent = "trying again every second";
    Critter.drawIcon(el.moodFace, "IDLE", true);
    setMoodButtonsAvailable(false);
    Scene.setOffline(true);
    showLcd("");
    showBar(0);
  }

  function setUnseen(v) {
    unseen = v;
    el.newTag.hidden = !v;
    updateTitle();
  }
  ["pointermove", "pointerdown", "keydown"].forEach(function (ev) {
    window.addEventListener(ev, function () { if (unseen && !document.hidden) setUnseen(false); }, { passive: true });
  });

  function updateTitle() {
    const label = current ? moodOf(current.state).label : "Claude Buddy";
    document.title = (unseen ? "(!) " : "") + label + " · Claude Buddy";
  }

  // ---------- timer ----------
  function fmt(sec) {
    sec = Math.max(0, Math.floor(sec));
    if (sec < 60) return sec + "s";
    const m = Math.floor(sec / 60);
    if (m < 60) return m + "m " + String(sec % 60).padStart(2, "0") + "s";
    return Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
  }
  function tick() {
    if (!current || isOffline()) return;
    const sec = current.seconds_in_state + (performance.now() - fetchedAt) / 1000;
    Stats.numText(el.moodTime, moodOf(current.state).blurb + " · " + fmt(sec));
    showBar(sec);
    updateTitle();
  }
  setInterval(tick, 250);

  // ---------- favicon ----------
  function setFavicon(mood) {
    const c = document.createElement("canvas");
    c.width = c.height = 36;
    Critter.drawIcon(c, mood);
    $("favicon").href = c.toDataURL();
  }

  // ---------- LCD message editor ----------
  const inputs = {};
  ORDER.forEach(function (mood) {
    const row = document.createElement("div");
    row.className = "msg-row";
    const id = "msg-" + mood.toLowerCase();
    const label = document.createElement("label");
    label.htmlFor = id;
    label.textContent = MOODS[mood].label;
    const input = document.createElement("input");
    input.id = id; input.name = mood; input.maxLength = LCD_WIDTH;
    input.autocomplete = "off"; input.spellcheck = false;
    input.setAttribute("aria-describedby", id + "-count " + id + "-err");
    const count = document.createElement("span");
    count.className = "count"; count.id = id + "-count";
    const err = document.createElement("p");
    err.className = "field-error"; err.id = id + "-err";
    row.append(faceIcon(mood), label, input, count, err);
    el.rows.appendChild(row);
    inputs[mood] = { input: input, count: count, err: err, row: row };

    input.addEventListener("input", function () { msgDirty = true; validate(mood); previewText = input.value; showLcd(previewText); });
    input.addEventListener("focus", function () { previewText = input.value; showLcd(previewText); });
    input.addEventListener("blur", function () { previewText = null; showLcd(current && !isOffline() ? current.text : ""); });
  });

  function problem(text) {
    if (text.length > LCD_WIDTH) return "Too long: " + text.length + " of " + LCD_WIDTH + " characters.";
    const bad = Array.from(new Set(text.replace(/[ -~]/g, "").split(""))).join("");
    if (bad) return "The screen can't show " + bad + ". Use plain letters, numbers and punctuation.";
    return "";
  }
  function validate(mood) {
    const f = inputs[mood];
    const msg = problem(f.input.value);
    Stats.numText(f.count, f.input.value.length + "/" + LCD_WIDTH);
    f.err.textContent = msg;
    f.row.classList.toggle("has-error", !!msg);
    f.input.setAttribute("aria-invalid", String(!!msg));
    refreshSave();
    return !msg;
  }
  // Save and Reset stay off until the messages have loaded (saving empty boxes would
  // wipe them) and while a save or reset is running. aria-disabled keeps keyboard focus.
  let msgLoaded = false;
  let msgBusy = false;
  let msgDirty = false; // typed since the last load, so a late load must not overwrite it
  function refreshSave() {
    const bad = ORDER.some(function (k) { return !!problem(inputs[k].input.value); });
    el.save.setAttribute("aria-disabled", String(!msgLoaded || msgBusy || bad));
    el.reset.setAttribute("aria-disabled", String(!msgLoaded || msgBusy));
  }
  function fill(messages) {
    ORDER.forEach(function (k) { inputs[k].input.value = messages[k] || ""; validate(k); });
    msgDirty = false;
  }
  async function loadMessages() {
    el.status.textContent = "Loading…";
    refreshSave();
    try {
      const m = await api("GET", "/messages");
      if (!msgDirty) fill(m);
      msgLoaded = true;
      el.status.textContent = "";
    } catch (e) {
      el.status.textContent = "Couldn't load the messages. Is the buddy service running?";
    }
    refreshSave();
  }
  async function runMessages(method, body, doneText, failText) {
    msgBusy = true;
    refreshSave();
    try {
      const saved = await api(method, "/messages", body);
      fill(saved);
      el.status.textContent = doneText;
      // the buddy shows the new text right away, so the preview should too
      if (current && current.state in saved && previewText === null) { current.text = saved[current.state]; showLcd(current.text); }
    } catch (err) {
      el.status.textContent = failText(err);
    }
    msgBusy = false;
    refreshSave();
  }

  // ---------- side panels: Stats and Settings, one open at a time ----------
  const stats = { toggle: $("stats-toggle"), panel: $("stats-panel"), close: $("stats-close") };
  function openStats() {
    if (!el.panel.hidden) closeSettings(true);
    stats.panel.hidden = false;
    stats.toggle.setAttribute("aria-expanded", "true");
    Stats.show($("stats-body"), Stats.SAMPLE, Array.from(stats.panel.querySelectorAll(".sc-range button")));
    stats.close.focus();
  }
  function closeStats(keepFocus) {
    stats.panel.hidden = true;
    stats.toggle.setAttribute("aria-expanded", "false");
    if (!keepFocus) stats.toggle.focus();
  }
  stats.toggle.addEventListener("click", function () { stats.panel.hidden ? openStats() : closeStats(); });
  stats.close.addEventListener("click", function () { closeStats(); });

  async function openSettings() {
    if (!stats.panel.hidden) closeStats(true);
    el.panel.hidden = false;
    el.toggle.setAttribute("aria-expanded", "true");
    const pressed = el.moodButtons.querySelector('[aria-pressed="true"]');
    (pressed || el.moodButtons.querySelector("button") || el.close).focus();
    loadMessages();
  }
  function closeSettings(keepFocus) {
    el.panel.hidden = true;
    showWheel(false);
    el.toggle.setAttribute("aria-expanded", "false");
    if (!keepFocus) el.toggle.focus();
  }
  el.toggle.addEventListener("click", function () { el.panel.hidden ? openSettings() : closeSettings(); });
  el.close.addEventListener("click", function () { closeSettings(); });
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (!el.panel.hidden) closeSettings();
    if (!stats.panel.hidden) closeStats();
  });

  el.form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (el.save.getAttribute("aria-disabled") === "true" || !ORDER.every(validate)) return;
    const body = {};
    ORDER.forEach(function (k) { body[k] = inputs[k].input.value; });
    el.status.textContent = "Saving…";
    runMessages("PUT", body, "Saved. The buddy will say these from now on.",
      function (err) { return "Not saved: " + err.message + "."; });
  });

  el.reset.addEventListener("click", function () {
    if (el.reset.getAttribute("aria-disabled") === "true") return;
    el.status.textContent = "Resetting…";
    runMessages("DELETE", undefined, "Back to the original messages.",
      function () { return "Couldn't reset. Is the buddy service running?"; });
  });

  let saved = null;
  try { saved = localStorage.getItem("buddy.color"); } catch (e) { /* no storage: use the default */ }
  setColor(/^#[0-9a-f]{6}$/i.test(saved || "") ? saved : DEFAULT_COLOR);
  showLcd("");
  poll();
})();
