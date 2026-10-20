(() => {
  "use strict";

  const REPO = "https://github.com/Rr1901/station-access-guide";
  const GROUPS = [
    { title: "Getting around", keys: ["lift", "escalator", "ramp_entry", "ramp_second", "ramp_fob", "battery_car", "boarding_ramp"] },
    { title: "Help on hand", keys: ["wheelchair", "wheelchair_booking", "human_assistance", "help_booth"] },
    { title: "Facilities", keys: ["accessible_toilet", "water_booth", "parking", "low_counter", "tactile_path", "braille_signage", "braille_map"] },
  ];
  const STATUS = {
    yes: { mark: "✓", text: "Available" },
    no: { mark: "✕", text: "Not available, according to official data" },
    not_listed: { mark: "–", text: "Not in the official list for this division" },
    unknown: { mark: "?", text: "No data yet" },
  };

  let data = null;
  let labels = {};
  let divisions = {};
  let active = -1;
  let current = [];

  const $ = (id) => document.getElementById(id);
  const q = $("q"), results = $("results"), statusEl = $("status");

  const norm = (s) => (s || "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]/g, "");
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Score a station against the query: exact code > name prefix > word prefix > substring > in-order letters.
  function score(st, query) {
    const nq = norm(query);
    if (!nq) return 0;
    if (st.code && norm(st.code) === nq) return 100;
    const names = [st.name, ...(st.aliases || [])];
    let best = 0;
    for (const n of names) {
      const nn = norm(n);
      if (nn === nq) best = Math.max(best, 95);
      else if (nn.startsWith(nq)) best = Math.max(best, 80);
      else if (n.toLowerCase().split(/\s+/).some((w) => norm(w).startsWith(nq))) best = Math.max(best, 70);
      else if (nn.includes(nq)) best = Math.max(best, 55);
      else if (nq.length >= 5 && subsequence(nq, nn)) best = Math.max(best, 30);
    }
    if (st.code && norm(st.code).startsWith(nq)) best = Math.max(best, 75);
    return best;
  }
  function subsequence(a, b) {
    let i = 0;
    for (const ch of b) if (ch === a[i]) i++;
    return i === a.length;
  }

  function countYes(st) {
    return Object.values(st.features).filter((f) => f.status === "yes").length;
  }

  function renderResults() {
    const query = q.value.trim();
    current = query
      ? data.stations.map((s) => [score(s, query), s]).filter(([sc]) => sc > 0)
          .sort((a, b) => b[0] - a[0] || a[1].name.localeCompare(b[1].name)).slice(0, 8).map(([, s]) => s)
      : [];
    active = current.length ? 0 : -1;
    results.innerHTML = current.map((s, i) => `
      <li role="option" id="opt-${i}" data-id="${esc(s.id)}" aria-selected="${i === active}">
        <span><span class="r-name">${esc(s.name)}</span>${s.code ? ` <span class="r-meta">${esc(s.code)}</span>` : ""}
        <br><span class="r-meta">${esc(s.division)} division · ${esc(s.zone)}</span></span>
        <span class="r-score">${countYes(s)} facilities</span>
      </li>`).join("");
    q.setAttribute("aria-expanded", current.length ? "true" : "false");
    q.setAttribute("aria-activedescendant", active >= 0 ? `opt-${active}` : "");
    statusEl.textContent = !query ? `${data.stations.length} stations so far`
      : current.length ? `${current.length} match${current.length > 1 ? "es" : ""}. Use arrow keys and Enter to open.`
      : "No station found. We only cover some divisions so far.";
  }

  function move(delta) {
    if (!current.length) return;
    active = (active + delta + current.length) % current.length;
    [...results.children].forEach((li, i) => li.setAttribute("aria-selected", i === active));
    q.setAttribute("aria-activedescendant", `opt-${active}`);
  }

  function linkify(note) {
    return esc(note).replace(/\b([6-9]\d{9})\b/g, '<a href="tel:+91$1">$1</a>');
  }

  function renderStation(id) {
    const st = data.stations.find((s) => s.id === id);
    const box = $("station");
    if (!st) {
      box.innerHTML = `<h1>Station not found</h1><p>It may not be covered yet.</p>`;
      return;
    }
    const counts = { yes: 0, not_listed: 0, unknown: 0 };
    Object.values(st.features).forEach((f) => counts[f.status === "no" ? "not_listed" : f.status]++);
    const div = divisions[st.division] || {};
    const issue = `${REPO}/issues/new?title=${encodeURIComponent(`Correction: ${st.name}`)}&body=${encodeURIComponent(`Station: ${st.name}${st.code ? ` (${st.code})` : ""}\n\nWhat is wrong or missing?\n\n`)}`;

    box.innerHTML = `
      <div class="st-head">
        <h1 tabindex="-1" id="st-title">${esc(st.name)}${st.code ? `<span class="st-code" aria-label="Station code ${esc(st.code)}">${esc(st.code)}</span>` : ""}</h1>
        <p class="st-sub">${esc(st.division)} division · ${esc(st.zone)}</p>
      </div>
      ${div.method === "secondary" ? `<div class="caveat"><p><strong>Not from an official station list.</strong> ${esc(div.method_note || "")} Call 139 or the station before you travel.</p>
        <ul>${(div.sources || []).map((x) => `<li><a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a></li>`).join("")}</ul></div>` : ""}
      <div class="summary">
        <div class="yes"><strong>${counts.yes}</strong><span>available</span></div>
        <div class="not_listed"><strong>${counts.not_listed}</strong><span>not available</span></div>
        <div class="unknown"><strong>${counts.unknown}</strong><span>no data yet</span></div>
      </div>
      ${GROUPS.map((g) => `
        <section class="group" aria-labelledby="g-${g.keys[0]}">
          <h2 id="g-${g.keys[0]}">${g.title}</h2>
          <ul class="feat">
            ${g.keys.map((k) => {
              const f = st.features[k] || { status: "unknown" };
              const s = STATUS[f.status];
              return `<li>
                <span class="mark ${f.status}" aria-hidden="true">${s.mark}</span>
                <div>
                  <div class="f-label">${esc(labels[k] || k)}</div>
                  <div class="f-status">${s.text}</div>
                  ${f.note ? `<div class="f-note">${linkify(f.note)}</div>` : ""}
                </div>
              </li>`;
            }).join("")}
          </ul>
        </section>`).join("")}
      <a class="report" href="${issue}" target="_blank" rel="noopener">Something wrong or missing? Tell us</a>
      <p class="src">Source: <a href="${esc(div.source_url || "#")}" target="_blank" rel="noopener">${esc(div.source_title || "Indian Railways")}</a>, checked ${esc(div.retrieved || "")}.
      ${st.features && Object.values(st.features).some((f) => f.status === "unknown") ? "“No data yet” means this division hasn't published that detail by station." : ""}</p>`;
    document.title = `${st.name} accessibility · Station Access Guide`;
    $("st-title").focus();
  }

  function route() {
    const m = location.hash.match(/^#\/s\/([a-z0-9-]+)/);
    $("view-search").hidden = !!m;
    $("view-station").hidden = !m;
    if (m) {
      renderStation(m[1]);
      window.scrollTo(0, 0);
    } else {
      document.title = "Station Access Guide";
      renderResults();
    }
  }

  function open(st) {
    if (st) location.hash = `#/s/${st.id}`;
  }

  q.addEventListener("input", renderResults);
  q.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Enter") { e.preventDefault(); open(current[active]); }
    else if (e.key === "Escape") { q.value = ""; renderResults(); }
  });
  results.addEventListener("click", (e) => {
    const li = e.target.closest("li[data-id]");
    if (li) open(data.stations.find((s) => s.id === li.dataset.id));
  });
  window.addEventListener("hashchange", route);

  fetch("data/stations.json")
    .then((r) => r.json())
    .then((d) => {
      data = d;
      d.features.forEach((f) => (labels[f.key] = f.label));
      d.divisions.forEach((v) => (divisions[v.division] = v));
      $("sources").innerHTML = "Data: " + d.divisions.map((v) =>
        `<a href="${esc(v.source_url)}" target="_blank" rel="noopener">${esc(v.division)} division</a> (checked ${esc(v.retrieved)})`).join(", ");
      route();
    })
    .catch(() => { statusEl.textContent = "Couldn't load station data. Please refresh."; });
})();
