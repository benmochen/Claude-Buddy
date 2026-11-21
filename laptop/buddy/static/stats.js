// The Stats card: one headline number, one chart, one comparison, then a short list.
// Week view answers "how long did Claude wait on me per day?", Today view shows the day itself.
(function () {
  "use strict";

  // shortcut: built-in sample data until the server keeps a daily log; swap for GET /stats then.
  // week: Monday to Sunday (null = no data); today's entry is computed from today.segments.
  // today.segments: [mood, startHour, endHour] in local time; phone is minutes, null without a camera.
  const SAMPLE = {
    week: [
      { waited: 52, worked: 318, prompts: 12, phone: 9, nags: 2 },
      { waited: 41, worked: 296, prompts: 10, phone: 4, nags: 1 },
      { waited: 68, worked: 352, prompts: 14, phone: 11, nags: 3 },
      { waited: 33, worked: 274, prompts: 8, phone: 3, nags: 0 },
      null, null, null,
    ],
    lastWeekAvgWaited: 59,
    today: {
      segments: [
        ["WORKING", 9.1, 9.35], ["DONE", 9.35, 9.42], ["WORKING", 9.42, 10.05], ["DONE", 10.05, 10.1],
        ["WORKING", 10.1, 10.6], ["DONE", 10.6, 10.75], ["ANNOYED", 10.75, 10.8], ["YELLING", 10.8, 10.86],
        ["WORKING", 10.86, 11.5], ["NEEDS_YOU", 11.5, 11.55], ["WORKING", 11.55, 12.1], ["DONE", 12.1, 12.2],
        ["IDLE", 12.2, 13.1], ["WORKING", 13.1, 14.0], ["DONE", 14.0, 14.05], ["WORKING", 14.05, 15.2],
        ["DONE", 15.2, 15.4], ["ANNOYED", 15.4, 15.45], ["WORKING", 15.45, 16.3], ["DONE", 16.3, 16.35],
        ["WORKING", 16.35, 17.1], ["DONE", 17.1, 17.3],
      ],
      phone: 6,
    },
  };

  const WAITING = ["DONE", "NEEDS_YOU", "ANNOYED", "YELLING"];
  const DAYS = ["M", "T", "W", "T", "F", "S", "S"];
  const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  let range = "week";

  // ---------- formatting ----------
  function hm(min) {
    min = Math.round(min);
    if (min < 60) return min + "m";
    return Math.floor(min / 60) + "h " + (min % 60) + "m";
  }
  function hourLabel(hour) { const hh = hour % 24; return (hh % 12 || 12) + (hh < 12 ? " am" : " pm"); }
  function todayIndex() { return (new Date().getDay() + 6) % 7; } // Monday = 0

  // ---------- numbers from today's mood changes ----------
  function summarizeDay(day) {
    const s = { waited: 0, worked: 0, prompts: 0, longest: 0, fastest: 0, nags: 0, phone: day.phone };
    let run = 0;
    const runs = [];
    day.segments.forEach(function (seg) {
      const min = (seg[2] - seg[1]) * 60;
      if (seg[0] === "WORKING") {
        if (run > 0) runs.push(run);
        run = 0;
        s.prompts++;
        s.worked += min;
      } else if (WAITING.indexOf(seg[0]) !== -1) {
        run += min;
        s.waited += min;
        if (seg[0] === "ANNOYED" || seg[0] === "YELLING") s.nags++;
      } else {
        run = 0; // quiet time ends a wait without a comeback
      }
    });
    if (runs.length) { s.longest = Math.max.apply(null, runs); s.fastest = Math.min.apply(null, runs); }
    return s;
  }
  function weekWithToday(data) {
    const t = todayIndex();
    const today = summarizeDay(data.today);
    const week = [];
    for (let i = 0; i < 7; i++) week.push(i < t ? data.week[i] : i === t ? today : null);
    return { week: week, today: today, t: t };
  }
  // Real data can be partial, unsorted or cross midnight; make it safe once, up front.
  function clean(data) {
    const today = data.today || {};
    const segs = [];
    (today.segments || []).forEach(function (seg) {
      const start = Number(seg[1]);
      let end = Number(seg[2]);
      if (end < start) end = 24; // crossed midnight: count it up to the end of today
      if (end > start) segs.push([seg[0], start, end]);
    });
    segs.sort(function (a, b) { return a[1] - b[1]; });
    const week = [];
    for (let i = 0; i < 7; i++) {
      const d = (data.week || [])[i];
      if (!d) { week.push(null); continue; }
      week.push({
        waited: Number(d.waited) || 0, worked: Number(d.worked) || 0, nags: Number(d.nags) || 0,
        phone: d.phone == null ? null : Number(d.phone) || 0,
      });
    }
    return {
      week: week,
      lastWeekAvgWaited: Number(data.lastWeekAvgWaited) || 0,
      today: { segments: segs, phone: today.phone == null ? null : Number(today.phone) || 0 },
    };
  }
  function mean(list) { return list.reduce(function (a, b) { return a + b; }, 0) / list.length; }

  // ---------- small DOM helpers ----------
  // Put text in an element with every number in the LCD face; the pixel font's 5 reads as S.
  function numText(target, text) {
    target.textContent = "";
    String(text).split(/(\d[\d:.,%/]*)/).forEach(function (part, i) {
      if (!part) return;
      if (i % 2) { const n = document.createElement("span"); n.className = "num"; n.textContent = part; target.appendChild(n); }
      else target.appendChild(document.createTextNode(part));
    });
    return target;
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) numText(e, text);
    return e;
  }
  function delta(label, diff) {
    // lower wait is better, so going down is good news
    const d = el("p", "sc-delta " + (diff <= 0 ? "is-good" : "is-bad"));
    // a stepped pixel arrow, down for good news, up for bad
    d.innerHTML = '<svg viewBox="0 0 5 5" aria-hidden="true"><path d="' +
      (diff <= 0 ? "M2 0h1v3h-1zM0 2h5v1h-5zM1 3h3v1h-3zM2 4h1v1h-1z" : "M2 0h1v1h-1zM1 1h3v1h-3zM0 2h5v1h-5zM2 3h1v2h-1z") +
      '" fill="currentColor"/></svg>';
    d.appendChild(numText(document.createElement("span"), label));
    return d;
  }
  function rows(items) {
    const list = el("ul", "sc-rows");
    items.forEach(function (it) {
      const li = el("li");
      const icon = el("span", "sc-icon");
      const c = document.createElement("canvas");
      c.width = 18; c.height = 12;
      c.setAttribute("aria-hidden", "true");
      Critter.drawIcon(c, it[0]);
      icon.appendChild(c);
      li.append(icon, el("span", "sc-row-label", it[1]), el("span", "sc-row-value", it[2]));
      list.appendChild(li);
    });
    return list;
  }
  // Bars in a dark well. bars: [{ value, nag, label, title }]; nag stacks on top in red.
  function barChart(bars, top, highlight, avg, ariaLabel) {
    const chart = el("div", "sc-chart");
    chart.setAttribute("role", "img");
    chart.setAttribute("aria-label", ariaLabel);
    const plot = el("div", "sc-plot");
    plot.style.setProperty("--cols", bars.length);
    if (avg !== null) {
      const avgLine = el("div", "sc-avg");
      avgLine.style.bottom = (avg / top * 100) + "%";
      avgLine.appendChild(el("span", "", "avg"));
      plot.appendChild(avgLine);
    }
    const labels = el("div", "sc-days");
    labels.style.setProperty("--cols", bars.length);
    bars.forEach(function (b, i) {
      const col = el("div", "sc-col");
      col.title = b.title;
      if (b.value === null) {
        col.appendChild(el("div", "sc-bar is-empty"));
      } else {
        // the column stacks bottom-up, so nag time lands on top of the wait
        const bar = el("div", "sc-bar" + (i === highlight ? " is-today" : ""));
        bar.style.height = Math.max(b.value > 0 ? 3 : 0, b.value / top * 100) + "%";
        col.appendChild(bar);
        if (b.nag) { const n = el("div", "sc-bar is-nag"); n.style.height = (b.nag / top * 100) + "%"; col.appendChild(n); }
      }
      plot.appendChild(col);
      labels.appendChild(el("span", i === highlight ? "is-today" : "", b.label));
    });
    chart.append(plot, labels);
    return chart;
  }

  function hero(label, value, deltaEl) {
    const box = el("div", "sc-hero");
    box.append(el("p", "sc-label", label), el("p", "sc-big", value));
    if (deltaEl) box.appendChild(deltaEl);
    return box;
  }

  // ---------- views ----------
  function empty(root, label, message) {
    const card = el("div");
    card.append(hero(label, "0m", null), el("p", "sc-empty", message));
    root.appendChild(card);
  }

  function renderWeek(root, data) {
    const w = weekWithToday(data);
    const days = [];
    w.week.forEach(function (d, i) { if (d && (i !== w.t || data.today.segments.length)) days.push(d); });
    if (!days.length) {
      empty(root, "Claude waited on you, daily average", "Nothing yet this week. Send Claude a prompt and check back.");
      return;
    }
    const waits = days.map(function (d) { return d.waited; });
    const avg = mean(waits);
    const pct = data.lastWeekAvgWaited ? Math.round((avg - data.lastWeekAvgWaited) / data.lastWeekAvgWaited * 100) : null;

    const top = Math.max(60, Math.ceil(Math.max.apply(null, waits.concat([avg])) / 30) * 30);
    const bars = w.week.map(function (d, i) {
      return { value: d ? d.waited : null, label: DAYS[i], title: DAY_NAMES[i] + (d ? ": " + hm(d.waited) : "") };
    });
    const chart = barChart(bars, top, w.t, avg, "Daily wait this week, average " + hm(avg));
    const card = el("div");
    card.append(hero("Claude waited on you, daily average", hm(avg),
      pct === null ? null : delta(Math.abs(pct) + "% " + (pct <= 0 ? "less" : "more") + " than last week", pct)), chart);

    // every row is a daily average, same as the headline, so nothing needs converting
    let worked = 0, phone = 0, nags = 0, phoneDays = 0;
    days.forEach(function (d) {
      worked += d.worked; nags += d.nags;
      if (d.phone !== null) { phone += d.phone; phoneDays++; }
    });
    root.append(card, rows([
      ["WORKING", "Claude worked", hm(worked / days.length) + " a day"],
      ["NEEDS_YOU", "Phone while Claude waited", phoneDays ? hm(phone / phoneDays) + " a day" : "Needs camera"],
      ["YELLING", "Nags", Math.round(nags / days.length) + " a day"],
    ]));
  }

  function renderDay(root, data) {
    const w = weekWithToday(data);
    const s = w.today;
    const past = [];
    w.week.forEach(function (d, i) { if (d && i !== w.t) past.push(d.waited); });
    const diff = past.length ? s.waited - mean(past) : null;

    // minutes waited in each hour of the day, nag time stacked on top
    const segs = data.today.segments;
    if (!segs.length) {
      empty(root, "Claude waited on you today", "Nothing yet today. Send Claude a prompt and check back.");
      return;
    }
    const from = Math.floor(segs[0][1]);
    let last = 0;
    segs.forEach(function (seg) { last = Math.max(last, seg[2]); });
    const to = Math.ceil(last);
    const hours = [];
    for (let hr = from; hr < to; hr++) hours.push({ wait: 0, nag: 0 });
    segs.forEach(function (seg) {
      if (WAITING.indexOf(seg[0]) === -1) return;
      const isNag = seg[0] === "ANNOYED" || seg[0] === "YELLING";
      for (let hr = Math.floor(seg[1]); hr < seg[2]; hr++) {
        const min = (Math.min(seg[2], hr + 1) - Math.max(seg[1], hr)) * 60;
        if (isNag) hours[hr - from].nag += min; else hours[hr - from].wait += min;
      }
    });
    const bars = hours.map(function (hh, i) {
      const hr = from + i;
      return {
        value: hh.wait, nag: hh.nag,
        label: (hr % 12 || 12) + "",
        title: hourLabel(hr) + ": " + hm(hh.wait + hh.nag) + " waiting" + (hh.nag ? ", " + hm(hh.nag) + " of it nagging" : ""),
      };
    });
    let peak = 0;
    hours.forEach(function (hh) { peak = Math.max(peak, hh.wait + hh.nag); });
    const top = Math.max(15, Math.ceil(peak / 5) * 5);
    // every hour is today, so no bar is singled out: all waiting bars share the legend's colour
    const chart = barChart(bars, top, -1, null, "Minutes Claude waited on you each hour today");
    chart.classList.add("is-day");
    const legend = el("ul", "sc-legend");
    [["wait", "Waiting on you"], ["nag", "Nagging"]].forEach(function (k) {
      const li = el("li");
      li.append(el("span", "sc-dot is-" + k[0]), k[1]);
      legend.appendChild(li);
    });

    const card = el("div");
    card.append(hero("Claude waited on you today", hm(s.waited),
      diff === null ? null : delta(hm(Math.abs(diff)) + " " + (diff <= 0 ? "less" : "more") + " than your average", diff)), chart, legend);
    root.append(card, rows([
      ["WORKING", "Claude worked", hm(s.worked)],
      ["DONE", "Longest wait", hm(s.longest)],
      ["NEEDS_YOU", "Phone while Claude waited", s.phone === null ? "Needs camera" : hm(s.phone)],
      ["YELLING", "Nags", String(s.nags)],
    ]));
  }

  // Week / Today switch, then draw the chosen view.
  function show(root, data, rangeButtons) {
    rangeButtons.forEach(function (b) {
      b.setAttribute("aria-pressed", String(b.dataset.range === range));
      b.onclick = function () { range = b.dataset.range; show(root, data, rangeButtons); };
    });
    root.textContent = "";
    if (range === "week") renderWeek(root, clean(data)); else renderDay(root, clean(data));
  }

  window.Stats = { SAMPLE: SAMPLE, show: show, numText: numText };
})();
