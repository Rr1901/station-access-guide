// Visitor video reports on station pages: show what visitors have seen, and let a signed-in
// visitor record a short video at the station. All checks that matter happen again on the
// server (supabase/functions/submit-report); the ones here just save people wasted effort.
import { CONFIG } from "./config.js";

const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.3/+esm";
const BUCKET = "report-videos";
const CONSENT_VERSION = "2026-10-22";
const MIN_S = 15, MAX_S = 60, MAX_BYTES = 12 * 1024 * 1024, GOOD_ACCURACY_M = 100;
const RECENT_DAYS = 90, CONFIRMATIONS = 2;
const RESUME_KEY = "railclub-report-resume";
// Facilities a video can show (same list as the server's VIDEO_FEATURES)
const VIDEO_FEATURES = ["lift", "escalator", "ramp_entry", "ramp_second", "ramp_fob", "accessible_toilet",
  "water_booth", "parking", "help_booth", "low_counter", "tactile_path", "braille_signage", "braille_map",
  "wheelchair", "battery_car", "boarding_ramp"];

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (d) => new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

let sb = null;
async function client() {
  if (!sb) {
    const { createClient } = await import(SUPABASE_JS);
    sb = createClient(CONFIG.supabaseUrl, CONFIG.supabaseKey, {
      auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true },
    });
  }
  return sb;
}

async function loadFacts(stationId) {
  const url = `${CONFIG.supabaseUrl}/rest/v1/facts?station_id=eq.${encodeURIComponent(stationId)}` +
    "&select=feature,note,seen_on&order=seen_on.desc&limit=200";
  try {
    const res = await fetch(url, { headers: { apikey: CONFIG.supabaseKey } });
    return res.ok ? await res.json() : [];
  } catch {
    return [];
  }
}

/** Gate 0: what a video here could still add (not official "yes", not confirmed recently). */
function stillNeeded(station, facts) {
  const since = new Date(Date.now() - RECENT_DAYS * 86400000).toISOString().slice(0, 10);
  const recent = {};
  for (const f of facts) if (f.seen_on >= since) recent[f.feature] = (recent[f.feature] || 0) + 1;
  return VIDEO_FEATURES.filter((k) => (station.features[k] || {}).status !== "yes" && (recent[k] || 0) < CONFIRMATIONS);
}

// ---------- coming back from Google sign-in ----------
// Google returns to the plain page URL with ?code=…; finish signing in, tidy the URL and go back
// to the station the visitor was reporting on.
(async () => {
  if (!CONFIG.visitorReports || !new URLSearchParams(location.search).has("code")) return;
  const c = await client();
  await c.auth.getSession(); // exchanges the code for a session
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(RESUME_KEY) || "null"); } catch { /* ignore */ }
  history.replaceState(null, "", location.pathname + (saved ? `#/s/${saved.station}` : location.hash));
  if (saved) window.dispatchEvent(new HashChangeEvent("hashchange"));
})();

// ---------- station page section ----------

let current = null; // { station, labels, facts }

document.addEventListener("station:shown", (e) => onStation(e.detail));
if (window.stationShown && document.getElementById("visitor-slot")) onStation(window.stationShown);

async function onStation({ station, labels }) {
  if (!CONFIG.visitorReports) return;
  const slot = document.getElementById("visitor-slot");
  if (!slot) return;
  current = { station, labels, facts: [] };
  slot.innerHTML = `<section class="group visitor" aria-labelledby="v-title">
      <h2 id="v-title">Seen by visitors</h2><p class="hint">Loading…</p></section>`;
  current.facts = await loadFacts(station.id);
  if (current?.station.id !== station.id) return; // user moved on
  renderSection(slot);
  resumeAfterSignIn();
}

function renderSection(slot) {
  const { station, labels, facts } = current;
  const byFeature = {};
  for (const f of facts) (byFeature[f.feature] ||= []).push(f);
  const items = Object.entries(byFeature).map(([k, list]) => `<li>
      <span class="mark yes" aria-hidden="true">✓</span>
      <div><div class="f-label">${esc(labels[k] || k)}</div>
      <div class="f-status">Seen by ${list.length > 1 ? `${list.length} visitors` : "a visitor"}, latest ${fmtDate(list[0].seen_on)}</div>
      ${list[0].note ? `<div class="f-note">${esc(list[0].note)}</div>` : ""}</div></li>`).join("");
  slot.innerHTML = `<section class="group visitor" aria-labelledby="v-title">
      <h2 id="v-title">Seen by visitors</h2>
      ${items ? `<ul class="feat">${items}</ul>` : `<p class="hint">No visitor reports yet for ${esc(station.name)}.</p>`}
      <p class="hint">Visitor reports are checked automatically and by a reviewer. Facilities can change, so call 139 or the station before you rely on one.</p>
      <button type="button" class="btn" id="add-video">📹 Add a video of this station</button>
      <div id="report-flow" class="flow" hidden aria-live="polite"></div>
    </section>`;
  document.getElementById("add-video").addEventListener("click", () => startFlow());
}

// ---------- the reporting flow ----------

const state = {};
const flowEl = () => document.getElementById("report-flow");

function show(html) {
  const el = flowEl();
  el.hidden = false;
  el.innerHTML = html;
  el.querySelector("h3")?.focus();
}

function startFlow(preselected = []) {
  const { station, labels, facts } = current;
  const needed = stillNeeded(station, facts);
  document.getElementById("add-video").hidden = true;
  if (!needed.length) {
    show(`<h3 tabindex="-1">Nothing missing here right now</h3>
      <p>Everything a video could show is already confirmed for ${esc(station.name)}. Thank you for helping!</p>`);
    return;
  }
  show(`<h3 tabindex="-1">1. What will you film?</h3>
    <p>Tick only what you can show in one short video (15–60 seconds). Not yet confirmed for ${esc(station.name)}:</p>
    <div class="ticks">${needed.map((k) => `<label><input type="checkbox" value="${k}" ${preselected.includes(k) ? "checked" : ""}> ${esc(labels[k] || k)}</label>`).join("")}</div>
    <button type="button" class="btn" id="f-next">Next</button> <button type="button" class="link" id="f-cancel">Cancel</button>`);
  document.getElementById("f-cancel").onclick = cancel;
  document.getElementById("f-next").onclick = async () => {
    state.features = [...flowEl().querySelectorAll("input:checked")].map((i) => i.value);
    if (!state.features.length) return alert("Tick at least one facility.");
    await stepSignIn();
  };
}

function cancel() {
  stopCamera();
  const el = flowEl();
  el.hidden = true;
  el.innerHTML = "";
  document.getElementById("add-video").hidden = false;
}

async function stepSignIn() {
  const c = await client();
  const { data } = await c.auth.getSession();
  if (data.session) return stepConsent(data.session.user);
  show(`<h3 tabindex="-1">2. Sign in</h3>
    <p>We use your Google account only to stop spam and to credit your reports. We never see your password.</p>
    <button type="button" class="btn" id="g-in">Sign in with Google</button> <button type="button" class="link" id="f-cancel">Cancel</button>`);
  document.getElementById("f-cancel").onclick = cancel;
  document.getElementById("g-in").onclick = async () => {
    try {
      sessionStorage.setItem(RESUME_KEY, JSON.stringify({ station: current.station.id, features: state.features }));
    } catch { /* storage blocked: the visitor just ticks again after signing in */ }
    await c.auth.signInWithOAuth({ provider: "google", options: { redirectTo: location.href.split("#")[0].split("?")[0] } });
  };
}

async function resumeAfterSignIn() {
  let saved = null;
  try {
    saved = JSON.parse(sessionStorage.getItem(RESUME_KEY) || "null");
  } catch { /* ignore */ }
  if (!saved || saved.station !== current.station.id) return;
  sessionStorage.removeItem(RESUME_KEY);
  const c = await client();
  const { data } = await c.auth.getSession();
  if (!data.session) return;
  state.features = saved.features;
  document.getElementById("add-video").hidden = true;
  stepConsent(data.session.user);
}

function stepConsent(user) {
  state.user = user;
  show(`<h3 tabindex="-1">3. Before you record</h3>
    <ul class="rules">
      <li>Film only the facility (lift, ramp, toilet sign…). <strong>Don't film people's faces.</strong></li>
      <li>Stay safe: keep away from the platform edge and never lean out of a train.</li>
      <li>No sound is recorded. We use your location only to check you're at the station.</li>
      <li>The video is deleted once it's checked. Only the facts are published, without your name.</li>
    </ul>
    <label class="consent"><input type="checkbox" id="c-ok"> I agree to the <a href="privacy.html" target="_blank" rel="noopener">privacy notice</a> and that the facts from my video can be published.</label>
    <p class="hint">Signed in as ${esc(user.email || "")}. <button type="button" class="link" id="sign-out">Sign out</button></p>
    <button type="button" class="btn" id="c-next">Next: check my location</button> <button type="button" class="link" id="f-cancel">Cancel</button>`);
  document.getElementById("f-cancel").onclick = cancel;
  document.getElementById("sign-out").onclick = async () => { await (await client()).auth.signOut(); cancel(); };
  document.getElementById("c-next").onclick = () => {
    if (!document.getElementById("c-ok").checked) return alert("Please tick the box to continue.");
    stepLocation();
  };
}

function stepLocation() {
  show(`<h3 tabindex="-1">4. Checking your location…</h3><p id="loc-msg">Allow location access when your phone asks.</p>`);
  if (!navigator.geolocation) return show(`<h3 tabindex="-1">Location isn't available</h3><p>This browser can't share your location, which we need to check you're at the station.</p>`);
  let best = null;
  const finish = () => {
    navigator.geolocation.clearWatch(watch);
    clearTimeout(timer);
    if (!best) {
      show(`<h3 tabindex="-1">We couldn't get your location</h3><p>Check location is allowed for this site, then try again.</p>
        <button type="button" class="btn" id="l-retry">Try again</button>`);
      document.getElementById("l-retry").onclick = stepLocation;
      return;
    }
    state.location = best;
    if (best.accuracy_m > GOOD_ACCURACY_M) {
      show(`<h3 tabindex="-1">Your location is too rough (±${Math.round(best.accuracy_m)} m)</h3>
        <p>Step outside the building or near a platform opening, then try again.</p>
        <button type="button" class="btn" id="l-retry">Try again</button>`);
      document.getElementById("l-retry").onclick = stepLocation;
      return;
    }
    stepRecord();
  };
  const watch = navigator.geolocation.watchPosition((p) => {
    const fix = { lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: p.coords.accuracy };
    if (!best || fix.accuracy_m < best.accuracy_m) best = fix;
    const msg = document.getElementById("loc-msg");
    if (msg) msg.textContent = `Accuracy ±${Math.round(fix.accuracy_m)} m…`;
    if (fix.accuracy_m <= 30) finish();
  }, () => finish(), { enableHighAccuracy: true, maximumAge: 0, timeout: 20000 });
  const timer = setTimeout(finish, 20000);
}

// ---------- camera ----------

let stream = null, recorder = null, sampler = null;

function stopCamera() {
  clearInterval(sampler);
  if (recorder && recorder.state !== "inactive") recorder.stop();
  stream?.getTracks().forEach((t) => t.stop());
  stream = recorder = null;
}

function pickMime() {
  for (const m of ["video/mp4", "video/webm;codecs=vp8", "video/webm"]) {
    if (window.MediaRecorder && MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

async function stepRecord() {
  const mime = pickMime();
  if (!mime || !navigator.mediaDevices?.getUserMedia) {
    return show(`<h3 tabindex="-1">Recording isn't supported here</h3><p>Please try in Chrome or Safari on your phone.</p>`);
  }
  show(`<h3 tabindex="-1">5. Record ${MIN_S}–${MAX_S} seconds</h3>
    <p class="hint">Tip: if you can, start with a platform sign or the station name board. It helps your report get approved faster.</p>
    <video id="cam" class="cam" autoplay muted playsinline></video>
    <p id="rec-time" class="rec-time" aria-live="off">0 s</p>
    <button type="button" class="btn" id="rec">● Start recording</button> <button type="button" class="link" id="f-cancel">Cancel</button>`);
  document.getElementById("f-cancel").onclick = cancel;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false, // never record sound
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
    });
  } catch {
    return show(`<h3 tabindex="-1">Camera not available</h3><p>Allow camera access for this site, then try again.</p>`);
  }
  const cam = document.getElementById("cam");
  cam.srcObject = stream;
  const btn = document.getElementById("rec");
  btn.onclick = () => {
    if (recorder) {
      if ((Date.now() - state.startedAt) / 1000 < MIN_S) return;
      recorder.stop();
      return;
    }
    const chunks = [];
    const frames = { total: 0, blank: 0 };
    recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 1_200_000 });
    recorder.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
    recorder.onstop = () => {
      clearInterval(sampler);
      clearInterval(tick);
      const duration = (Date.now() - state.startedAt) / 1000;
      const type = mime.split(";")[0];
      const blob = new Blob(chunks, { type });
      stopCamera();
      if (frames.total && frames.blank / frames.total > 0.7) {
        return retry("The video looks too dark or the camera was covered.");
      }
      if (blob.size > MAX_BYTES) return retry("The video is too large. Please record a shorter one.");
      state.video = { blob, type, ext: type === "video/mp4" ? "mp4" : "webm", duration };
      stepSend();
    };
    state.startedAt = Date.now();
    state.recordedAt = new Date().toISOString();
    recorder.start(1000);
    btn.textContent = `■ Stop (after ${MIN_S} s)`;
    // Sample small frames to catch a covered lens or a black video before uploading
    const canvas = document.createElement("canvas");
    canvas.width = 32; canvas.height = 18;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    sampler = setInterval(() => {
      ctx.drawImage(cam, 0, 0, 32, 18);
      const px = ctx.getImageData(0, 0, 32, 18).data;
      let sum = 0, sq = 0;
      for (let i = 0; i < px.length; i += 4) {
        const y = 0.299 * px[i] + 0.587 * px[i + 1] + 0.114 * px[i + 2];
        sum += y; sq += y * y;
      }
      const n = px.length / 4, mean = sum / n, sd = Math.sqrt(Math.max(sq / n - mean * mean, 0));
      frames.total++;
      if (mean < 20 || sd < 6) frames.blank++;
    }, 1500);
    const tick = setInterval(() => {
      const s = Math.floor((Date.now() - state.startedAt) / 1000);
      const t = document.getElementById("rec-time");
      if (t) t.textContent = `${s} s`;
      if (s >= MIN_S) btn.textContent = "■ Stop";
      if (s >= MAX_S && recorder?.state === "recording") recorder.stop();
    }, 500);
  };
}

function retry(message) {
  show(`<h3 tabindex="-1">Let's try that again</h3><p>${esc(message)}</p>
    <button type="button" class="btn" id="r-again">Record again</button> <button type="button" class="link" id="f-cancel">Cancel</button>`);
  document.getElementById("f-cancel").onclick = cancel;
  document.getElementById("r-again").onclick = stepRecord;
}

async function stepSend() {
  show(`<h3 tabindex="-1">6. Sending…</h3><p id="send-msg">Uploading your video…</p>`);
  const c = await client();
  const path = `${state.user.id}/${crypto.randomUUID()}.${state.video.ext}`;
  const up = await c.storage.from(BUCKET).upload(path, state.video.blob, { contentType: state.video.type, upsert: false });
  if (up.error) return retry("The upload didn't work. Check your connection and try again.");
  document.getElementById("send-msg").textContent = "Checking your video (this can take up to a minute)…";
  const { data, error } = await c.functions.invoke("submit-report", {
    body: {
      station_id: current.station.id, features: state.features,
      lat: state.location.lat, lon: state.location.lon, accuracy_m: state.location.accuracy_m,
      duration_s: state.video.duration, recorded_at: state.recordedAt, video_path: path,
      consent_version: CONSENT_VERSION,
    },
  });
  if (error) {
    let msg = "Something went wrong. Please try again later.";
    try { msg = (await error.context.json()).error || msg; } catch { /* keep default */ }
    return show(`<h3 tabindex="-1">Not sent</h3><p>${esc(msg)}</p>`);
  }
  const labels = current.labels;
  const reasons = (data.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("");
  const done = {
    published: `<h3 tabindex="-1">✅ Published, thank you!</h3><p>Now showing on this page: ${(data.published || []).map((k) => esc(labels[k] || k)).join(", ")}.</p>`,
    pending: `<h3 tabindex="-1">🕐 Thanks! A reviewer will check it</h3><p>Your report passed the automatic checks and is waiting for a person to confirm it.</p>${reasons ? `<ul>${reasons}</ul>` : ""}`,
    not_needed: `<h3 tabindex="-1">Thank you!</h3><p>${esc((data.reasons || [])[0] || "This is already confirmed.")}</p>`,
    rejected: `<h3 tabindex="-1">Not accepted</h3>${reasons ? `<ul>${reasons}</ul>` : ""}<p>Your video has been deleted.</p>`,
  };
  show(done[data.status] || done.pending);
  if (data.status === "published") {
    current.facts = await loadFacts(current.station.id);
    renderSection(document.getElementById("visitor-slot"));
  }
}
