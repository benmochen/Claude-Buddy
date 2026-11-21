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

  function faceIcon(mood) {
    const c = document.createElement("canvas");
    c.width = 18; c.height = 12;
    c.className = "face";
    c.setAttribute("aria-hidden", "true");
    Critter.drawIcon(c, mood);
    return c;
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
    b.addEventListener("click", function () { setMood(mood, b); });
    el.moodButtons.appendChild(b);
    moodBtns[mood] = b;
  });

  async function setMood(mood, btn) {
    btn.disabled = true;
    try {
      apply(await api("POST", "/mood", { state: mood }));
    } catch (err) {
      goOffline();
    } finally {
      btn.disabled = current === null;
    }
  }

  // ---------- status polling ----------
  async function poll() {
    try {
      apply(await api("GET", "/status"));
    } catch (err) {
      goOffline();
    }
    setTimeout(poll, POLL_MS);
  }

  function apply(s) {
    const wasOffline = document.body.classList.contains("is-offline");
    current = s;
    fetchedAt = performance.now();
    document.body.classList.remove("is-offline");
    el.offline.hidden = true;
    Scene.setOffline(false);
    Object.values(moodBtns).forEach(function (b) { b.disabled = false; });

    const first = lastChange === null;
    const changed = !first && s.change_id !== lastChange;
    lastChange = s.change_id;

    if (first || changed || wasOffline) {
      const m = MOODS[s.state] || MOODS.IDLE;
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
      // Claude itself finished or needs you: flag it until you've looked.
      const wantsYou = s.state !== "IDLE" && s.state !== "WORKING";
      setUnseen(changed && s.source !== "manual" && wantsYou);
    }
    if (previewText === null) showLcd(s.text);
    tick();
  }

  function goOffline() {
    document.body.classList.add("is-offline");
    el.offline.hidden = false;
    el.moodName.textContent = "Can't find the buddy";
    el.moodTime.textContent = "trying again every second";
    Critter.drawIcon(el.moodFace, "IDLE", true);
    Object.values(moodBtns).forEach(function (b) { b.disabled = true; });
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
    const label = current ? MOODS[current.state].label : "Claude Buddy";
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
    if (!current || document.body.classList.contains("is-offline")) return;
    const sec = current.seconds_in_state + (performance.now() - fetchedAt) / 1000;
    el.moodTime.textContent = MOODS[current.state].blurb + " · " + fmt(sec);
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

    input.addEventListener("input", function () { validate(mood); previewText = input.value; showLcd(previewText); });
    input.addEventListener("focus", function () { previewText = input.value; showLcd(previewText); });
    input.addEventListener("blur", function () { previewText = null; if (current) showLcd(current.text); });
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
    f.count.textContent = f.input.value.length + "/" + LCD_WIDTH;
    f.err.textContent = msg;
    f.row.classList.toggle("has-error", !!msg);
    f.input.setAttribute("aria-invalid", String(!!msg));
    refreshSave();
    return !msg;
  }
  function refreshSave() {
    el.save.disabled = ORDER.some(function (k) { return !!problem(inputs[k].input.value); });
  }
  function fill(messages) {
    ORDER.forEach(function (k) { inputs[k].input.value = messages[k] || ""; validate(k); });
  }

  async function openSettings() {
    el.panel.hidden = false;
    el.toggle.setAttribute("aria-expanded", "true");
    const pressed = el.moodButtons.querySelector('[aria-pressed="true"]');
    (pressed || el.moodButtons.querySelector("button") || el.close).focus();
    el.status.textContent = "Loading…";
    try {
      fill(await api("GET", "/messages"));
      el.status.textContent = "";
    } catch (e) {
      el.status.textContent = "Couldn't load the messages. Is the buddy service running?";
    }
  }
  function closeSettings() {
    el.panel.hidden = true;
    el.toggle.setAttribute("aria-expanded", "false");
    el.toggle.focus();
  }
  el.toggle.addEventListener("click", function () { el.panel.hidden ? openSettings() : closeSettings(); });
  el.close.addEventListener("click", closeSettings);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !el.panel.hidden) closeSettings(); });

  el.form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (!ORDER.every(validate)) return;
    const body = {};
    ORDER.forEach(function (k) { body[k] = inputs[k].input.value; });
    el.save.disabled = true;
    el.status.textContent = "Saving…";
    try {
      fill(await api("PUT", "/messages", body));
      el.status.textContent = "Saved. The buddy will say these from now on.";
    } catch (err) {
      el.status.textContent = "Not saved: " + err.message + ".";
    } finally {
      refreshSave();
    }
  });

  el.reset.addEventListener("click", async function () {
    el.status.textContent = "Resetting…";
    try {
      fill(await api("DELETE", "/messages"));
      el.status.textContent = "Back to the original messages.";
    } catch (e) {
      el.status.textContent = "Couldn't reset. Is the buddy service running?";
    }
  });

  showLcd("");
  poll();
})();
