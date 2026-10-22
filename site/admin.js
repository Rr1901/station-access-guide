// Review queue for admins. The page itself holds no secrets: every action goes through the
// review-report Edge Function, which checks the signed-in account is in the admins table.
import { CONFIG } from "./config.js";

const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.3/+esm";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (id) => document.getElementById(id);

const { createClient } = await import(SUPABASE_JS);
const sb = createClient(CONFIG.supabaseUrl, CONFIG.supabaseKey, {
  auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true },
});

async function call(body) {
  const { data, error } = await sb.functions.invoke("review-report", { body });
  if (error) {
    let msg = "Request failed";
    try { msg = (await error.context.json()).error || msg; } catch { /* keep default */ }
    throw new Error(msg);
  }
  return data;
}

async function main() {
  const { data } = await sb.auth.getSession();
  if (new URLSearchParams(location.search).has("code")) history.replaceState(null, "", location.pathname);
  if (!data.session) {
    $("queue").innerHTML = `<button type="button" class="btn" id="g-in">Sign in with Google</button>`;
    $("g-in").onclick = () => sb.auth.signInWithOAuth({ provider: "google",
      options: { redirectTo: location.href.split("?")[0].split("#")[0] } });
    return;
  }
  $("who").innerHTML = `Signed in as ${esc(data.session.user.email)} · <button type="button" class="link" id="out">Sign out</button>`;
  $("out").onclick = async () => { await sb.auth.signOut(); location.reload(); };
  await load();
}

async function load() {
  let res;
  try {
    res = await call({ action: "list" });
  } catch (e) {
    $("queue").innerHTML = `<p>${esc(e.message)}</p>`;
    return;
  }
  const { items, features } = res;
  if (!items.length) {
    $("queue").innerHTML = `<p>Nothing waiting. 🎉</p>`;
    return;
  }
  $("queue").innerHTML = `<p class="hint">${items.length} waiting, oldest first. Video links expire after 10 minutes; reload the page for fresh ones.</p>` +
    items.map((r) => card(r, features)).join("");
  for (const r of items) {
    $(`ok-${r.id}`).onclick = () => decide(r.id, "approve");
    $(`no-${r.id}`).onclick = () => decide(r.id, "reject");
  }
}

function card(r, features) {
  const g = r.gemini;
  const seen = new Map((g?.features ?? []).map((f) => [f.key, f]));
  const ticks = r.claimed_features.map((k) => {
    const f = seen.get(k);
    const info = f ? ` <span class="hint">(Gemini: ${f.seen ? `seen, ${esc(f.confidence)}${f.at ? ` at ${esc(f.at)}` : ""}${f.where ? `, ${esc(f.where)}` : ""}` : "not seen"})</span>` : "";
    return `<label><input type="checkbox" name="f-${r.id}" value="${esc(k)}" ${r.suggested_features.includes(k) ? "checked" : ""}> ${esc(features[k] || k)}${info}</label>`;
  }).join("");
  const gem = g ? [
    `railway station: ${g.is_railway_station ? "yes" : "NO"}`,
    `inside station: ${g.inside_station_premises ? "yes" : "NO"}`,
    `board: ${g.station_board_visible ? `"${esc(g.station_board_text)}" (${esc(g.board_matches_station)})` : "not visible"}`,
    g.is_screen_or_recording_of_screen ? "<strong>SCREEN</strong>" : "",
    g.looks_edited ? "<strong>EDITED</strong>" : "",
    g.notes ? esc(g.notes) : "",
  ].filter(Boolean).join(" · ") : "Not checked by Gemini";
  return `<article class="card">
    <h2>${esc(r.station)}</h2>
    ${r.video_url ? `<video src="${esc(r.video_url)}" controls muted playsinline preload="metadata"></video>` : "<p>Video missing</p>"}
    <dl>
      <dt>Recorded</dt><dd>${esc(new Date(r.recorded_at).toLocaleString("en-IN"))} · ${Math.round(r.duration_s ?? 0)} s</dd>
      <dt>Location</dt><dd>${r.distance_m == null ? "no station coordinates on file" : `${esc(r.distance_m)} m from station`} (±${Math.round(r.accuracy_m ?? 0)} m)</dd>
      <dt>Contributor</dt><dd>${r.contributor.approved} approved, ${r.contributor.rejected} rejected before</dd>
      <dt>Why here</dt><dd>${(r.reasons ?? []).map(esc).join("; ")}</dd>
      <dt>Gemini</dt><dd>${gem}</dd>
    </dl>
    <fieldset class="ticks"><legend>Publish these facilities</legend>${ticks}</fieldset>
    <div class="actions">
      <button type="button" class="btn" id="ok-${r.id}">Approve</button>
      <input type="text" id="why-${r.id}" placeholder="Reason, if rejecting" aria-label="Reason for rejecting">
      <button type="button" class="btn danger" id="no-${r.id}">Reject</button>
    </div>
  </article>`;
}

async function decide(id, action) {
  const body = { action, report_id: id };
  if (action === "approve") {
    body.features = [...document.querySelectorAll(`input[name="f-${id}"]:checked`)].map((i) => i.value);
    if (!body.features.length) return alert("Tick at least one facility to publish, or reject the report.");
  } else {
    body.reason = $(`why-${id}`).value;
  }
  document.querySelectorAll(`#ok-${id}, #no-${id}`).forEach((b) => (b.disabled = true));
  try {
    await call(body);
  } catch (e) {
    alert(e.message);
  }
  await load();
}

main();
