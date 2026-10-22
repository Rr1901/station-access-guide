// POST /functions/v1/submit-report
// A signed-in visitor has uploaded a video to report-videos/<their id>/<file>; run it through
// the gates, ask Gemini only if every free check passes, then publish, queue or reject.
import { encodeBase64 } from "jsr:@std/encoding@1.0.10/base64";
import {
  decide, gateBudget, gateContributor, gateDuplicate, gateFile, gateLimits, gateLocation, gateNeeded,
  gateRecording, type Outcome, parseInput, stillNeeded,
} from "../_shared/rules.ts";
import { checkVideo, PROMPT_VERSION } from "../_shared/gemini.ts";
import {
  adminClient, BUCKET, currentUser, istDate, istStartOf, loadLimits, loadStations, preflight, reply,
} from "../_shared/server.ts";

const MODEL = Deno.env.get("GEMINI_MODEL") ?? "gemini-2.5-flash";

Deno.serve(async (req) => {
  const early = preflight(req);
  if (early) return early;

  const admin = adminClient();
  const user = await currentUser(req, admin);
  if (!user) return reply(req, { error: "Please sign in" }, 401);

  const input = parseInput(await req.json().catch(() => null), user.id);
  if (typeof input === "string") return reply(req, { error: input }, 400);
  const station = (await loadStations())[input.station_id];
  if (!station) return reply(req, { error: "Unknown station" }, 400);

  const limits = await loadLimits(admin);
  const now = new Date();
  const base = {
    user_id: user.id, station_id: input.station_id, claimed_features: input.features,
    lat: input.lat, lon: input.lon, accuracy_m: input.accuracy_m, duration_s: input.duration_s,
    recorded_at: input.recorded_at, consent_version: input.consent_version, video_path: input.video_path,
  };
  const removeVideo = () => admin.storage.from(BUCKET).remove([input.video_path]);

  // Saves the report and answers the visitor. Videos are kept only while waiting for a reviewer.
  async function finish(status: string, decidedBy: string, reasons: string[], extra: Record<string, unknown> = {}) {
    const { data, error } = await admin.from("reports")
      .insert({ ...base, status, decided_by: decidedBy, reasons, ...extra }).select("id").single();
    if (status !== "pending") await removeVideo();
    if (error) {
      console.error("report insert failed", error.message);
      return reply(req, { error: "Something went wrong saving your report" }, 500);
    }
    return reply(req, { id: data.id, status, reasons, published: extra.published_features ?? [] });
  }
  const stopAt = (o: Outcome, extra: Record<string, unknown> = {}) =>
    o.ok ? null : finish(o.status, o.gate, [o.reason], extra);

  // ---- free gates, cheapest first ----
  const { data: contributor } = await admin.from("contributors")
    .select("approved_count, rejected_count, blocked").eq("user_id", user.id).maybeSingle();
  let r = stopAt(gateContributor(contributor));
  if (r) return r;

  const dayStart = istStartOf("day", now);
  const [{ count: userToday }, { count: stationToday }] = await Promise.all([
    admin.from("reports").select("id", { count: "exact", head: true }).eq("user_id", user.id).gte("created_at", dayStart),
    admin.from("reports").select("id", { count: "exact", head: true }).eq("station_id", input.station_id)
      .gte("created_at", dayStart),
  ]);
  r = stopAt(gateLimits(userToday ?? 0, stationToday ?? 0, limits));
  if (r) return r;

  const loc = gateLocation(input.station_id, station, input.lat, input.lon, input.accuracy_m, limits);
  r = stopAt(loc, { distance_m: loc.distance_m });
  if (r) return r;
  const located = { distance_m: loc.distance_m };

  const [folder, file] = input.video_path.split("/");
  const { data: listed } = await admin.storage.from(BUCKET).list(folder, { search: file, limit: 1 });
  const obj = listed?.find((o) => o.name === file);
  if (!obj) return reply(req, { error: "The video didn't upload. Please try again" }, 400);
  const size = Number(obj.metadata?.size ?? 0), mimetype = String(obj.metadata?.mimetype ?? "");
  r = stopAt(gateRecording(input.duration_s, input.recorded_at, obj.created_at ?? "", now, limits), located)
    ?? stopAt(gateFile(size, mimetype, limits), located);
  if (r) return r;

  const { data: blob, error: dlError } = await admin.storage.from(BUCKET).download(input.video_path);
  if (dlError || !blob) return reply(req, { error: "The video didn't upload. Please try again" }, 400);
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const sha = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
    .map((b) => b.toString(16).padStart(2, "0")).join("");
  const { data: dup } = await admin.from("reports").select("id").eq("video_sha256", sha).maybeSingle();
  r = stopAt(gateDuplicate(!!dup), located);
  if (r) return r;
  const hashed = { ...located, video_sha256: sha };

  const since = new Date(now.getTime() - limits.confirmed_within_days * 86_400_000).toISOString().slice(0, 10);
  const { data: recent } = await admin.from("facts").select("feature")
    .eq("station_id", input.station_id).gte("seen_on", since).in("feature", input.features);
  const counts: Record<string, number> = {};
  for (const f of recent ?? []) counts[f.feature] = (counts[f.feature] ?? 0) + 1;
  const needed = stillNeeded(input.features, station, counts, limits);
  r = stopAt(gateNeeded(needed), hashed);
  if (r) return r;

  const { count: monthCalls } = await admin.from("reports").select("id", { count: "exact", head: true })
    .not("gemini_model", "is", null).gte("created_at", istStartOf("month", now));
  r = stopAt(gateBudget(monthCalls ?? 0, limits), { ...hashed, suggested_features: needed });
  if (r) return r;

  // ---- Gemini: only now, and only about what's still needed ----
  const apiKey = Deno.env.get("GEMINI_API_KEY");
  if (!apiKey) {
    return finish("pending", "budget", ["Waiting for a reviewer"], { ...hashed, suggested_features: needed });
  }
  const call = await checkVideo({
    apiKey, model: MODEL, videoBase64: encodeBase64(bytes), mimeType: mimetype.split(";")[0],
    station, claimed: needed,
  });
  const geminiInfo = { ...hashed, gemini: call.result, gemini_model: MODEL, prompt_version: PROMPT_VERSION,
    gemini_tokens: call.tokens, gemini_ms: call.ms };
  if (!call.result) {
    // No usable answer: never guess, let a person decide
    console.error("gemini", call.error);
    return finish("pending", "gemini-error", ["Waiting for a reviewer"], { ...geminiInfo, suggested_features: needed });
  }

  const d = decide(call.result, needed, {
    has_coords: loc.has_coords, approved: contributor?.approved_count ?? 0, rejected: contributor?.rejected_count ?? 0,
    limits, stationName: station.name,
  });
  const confirmedKeys = d.confirmed.map((f) => f.key);

  if (d.status === "published") {
    const res = await finish("published", "rules", d.reasons,
      { ...geminiInfo, suggested_features: confirmedKeys, published_features: confirmedKeys });
    const saved = await res.clone().json();
    if (saved.id) {
      const seenOn = istDate(input.recorded_at);
      await admin.from("facts").insert(d.confirmed.map((f) => ({
        station_id: input.station_id, feature: f.key, note: f.where || null, seen_on: seenOn, report_id: saved.id,
      })));
      await admin.rpc("bump_contributor", { p_user: user.id, p_approved: 1, p_rejected: 0 });
    }
    return res;
  }
  if (d.status === "rejected") {
    await admin.rpc("bump_contributor", { p_user: user.id, p_approved: 0, p_rejected: 1 });
  }
  return finish(d.status, "rules", d.reasons, { ...geminiInfo, suggested_features: confirmedKeys });
});
