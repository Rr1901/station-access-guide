// deno test supabase/functions/tests/
import { assert, assertEquals } from "jsr:@std/assert@1.0.13";
import {
  decide, distanceM, gateBudget, gateContributor, gateDuplicate, gateFile, gateLimits, gateLocation, gateNeeded,
  gateRecording, type GeminiResult, type Limits, parseInput, type Station, stillNeeded,
} from "../_shared/rules.ts";
import { buildPrompt, checkVideo, parseResult } from "../_shared/gemini.ts";

const L: Limits = {
  per_user_per_day: 3, per_station_per_day: 20, min_seconds: 15, max_seconds: 60, max_bytes: 12_582_912,
  radius_m: 400, radius_overrides_m: { kalyan: 600 }, max_accuracy_m: 100, max_upload_age_min: 10,
  trust_after_approved: 3, distrust_after_rejected: 3, confirmed_reports_needed: 2, confirmed_within_days: 90,
  pending_keep_days: 14, monthly_gemini_calls: 300,
};
const KALYAN: Station = { name: "Kalyan", code: "KYN", division: "Mumbai", aliases: [],
  official_yes: ["lift", "ramp_entry"], lat: 19.2357, lon: 73.1297 };
const UID = "3f1c2d4e-1111-2222-3333-444455556666";
const okInput = {
  station_id: "kalyan", features: ["accessible_toilet", "escalator"], lat: 19.2360, lon: 73.1300, accuracy_m: 20,
  duration_s: 25, recorded_at: "2026-10-22T05:00:00Z", video_path: `${UID}/abcdef1234.webm`, consent_version: "v1",
};

Deno.test("input: valid report passes, tricks don't", () => {
  assertEquals(typeof parseInput(okInput, UID), "object");
  assertEquals(parseInput({ ...okInput, video_path: `someone-else/abcdef1234.webm` }, UID), "Invalid video path");
  assertEquals(parseInput({ ...okInput, video_path: `${UID}/../x/abcdef1234.webm` }, UID), "Invalid video path");
  assertEquals(parseInput({ ...okInput, features: ["wheelchair_booking"] }, UID), "Unknown facility");
  assertEquals(parseInput({ ...okInput, features: [] }, UID), "Tick between 1 and 8 facilities");
  assertEquals(parseInput({ ...okInput, lat: "19" }, UID), "Location missing");
  assertEquals(parseInput({ ...okInput, station_id: "Kalyan Jn!" }, UID), "Unknown station");
});

Deno.test("contributor and daily limits", () => {
  assert(gateContributor(null).ok);
  assertEquals(gateContributor({ blocked: true }).ok, false);
  assert(gateLimits(2, 19, L).ok);
  assertEquals(gateLimits(3, 0, L).ok, false);
  assertEquals(gateLimits(0, 20, L).ok, false);
});

Deno.test("location: inside, outside, big-station radius, weak GPS, no coordinates", () => {
  const inside = gateLocation("kalyan", KALYAN, 19.2360, 73.1300, 20, L);
  assert(inside.ok && inside.distance_m! < 100);
  // ~550 m away: outside the default 400 m, inside Kalyan's 600 m override
  assert(gateLocation("kalyan", KALYAN, 19.2406, 73.1297, 20, L).ok);
  assertEquals(gateLocation("other", KALYAN, 19.2406, 73.1297, 20, L).ok, false);
  assertEquals(gateLocation("kalyan", KALYAN, 19.30, 73.13, 20, L).ok, false);          // ~7 km away
  assertEquals(gateLocation("kalyan", KALYAN, 19.2360, 73.1300, 250, L).ok, false);     // GPS too vague
  const noCoords = gateLocation("x", { ...KALYAN, lat: undefined, lon: undefined }, 0, 0, 20, L);
  assert(noCoords.ok && !noCoords.has_coords);
  assert(Math.abs(distanceM(19.2357, 73.1297, 19.2406, 73.1297) - 545) < 10);
});

Deno.test("recording must be fresh and the right length", () => {
  const now = new Date("2026-10-22T05:03:00Z");
  assert(gateRecording(25, "2026-10-22T05:00:00Z", "2026-10-22T05:01:00Z", now, L).ok);
  assertEquals(gateRecording(5, "2026-10-22T05:00:00Z", "2026-10-22T05:01:00Z", now, L).ok, false);
  assertEquals(gateRecording(90, "2026-10-22T05:00:00Z", "2026-10-22T05:01:00Z", now, L).ok, false);
  assertEquals(gateRecording(25, "2026-10-21T05:00:00Z", "2026-10-22T05:01:00Z", now, L).ok, false); // old video
  assertEquals(gateRecording(25, "2026-10-22T05:00:00Z", "2026-10-22T04:30:00Z", now, L).ok, false); // stale upload
});

Deno.test("file, duplicate, budget", () => {
  assert(gateFile(9_000_000, "video/webm", L).ok);
  assert(gateFile(9_000_000, "video/mp4", L).ok);
  assertEquals(gateFile(20_000_000, "video/webm", L).ok, false);
  assertEquals(gateFile(1000, "image/png", L).ok, false);
  assertEquals(gateDuplicate(true).ok, false);
  assert(gateBudget(299, L).ok);
  const over = gateBudget(300, L);
  assert(!over.ok && over.status === "pending"); // over budget waits for a person, it isn't rejected
});

Deno.test("still needed: skips official yes and features confirmed twice recently", () => {
  const needed = stillNeeded(["lift", "accessible_toilet", "escalator", "tactile_path"], KALYAN,
    { escalator: 2, tactile_path: 1 }, L);
  assertEquals(needed, ["accessible_toilet", "tactile_path"]);
  const none = gateNeeded(stillNeeded(["lift"], KALYAN, {}, L));
  assert(!none.ok && none.status === "not_needed");
});

const good: GeminiResult = {
  is_railway_station: true, inside_station_premises: true, station_board_visible: false, station_board_text: "",
  board_matches_station: "not_visible", is_screen_or_recording_of_screen: false, looks_edited: false,
  unsafe_or_inappropriate: false, notes: "",
  features: [{ key: "accessible_toilet", seen: true, where: "PF 1, near stairs", at: "0:12", confidence: "high" }],
};
const ctx = { has_coords: true, approved: 5, rejected: 0, limits: L, stationName: "Kalyan" };

Deno.test("decide: trusted contributor, clear video, no board needed → published", () => {
  const d = decide(good, ["accessible_toilet"], ctx);
  assertEquals(d.status, "published");
  assertEquals(d.confirmed.map((f) => f.key), ["accessible_toilet"]);
});

Deno.test("decide: first reports, missing coordinates and medium confidence go to a person", () => {
  assertEquals(decide(good, ["accessible_toilet"], { ...ctx, approved: 0 }).status, "pending");
  assertEquals(decide(good, ["accessible_toilet"], { ...ctx, has_coords: false }).status, "pending");
  assertEquals(decide(good, ["accessible_toilet"], { ...ctx, rejected: 3 }).status, "pending");
  const medium = { ...good, features: [{ ...good.features[0], confidence: "medium" as const }] };
  assertEquals(decide(medium, ["accessible_toilet"], ctx).status, "pending");
});

Deno.test("decide: rejections", () => {
  const no = (patch: Partial<GeminiResult>) => decide({ ...good, ...patch }, ["accessible_toilet"], ctx).status;
  assertEquals(no({ is_railway_station: false }), "rejected");
  assertEquals(no({ inside_station_premises: false }), "rejected"); // mall escalator next door
  assertEquals(no({ is_screen_or_recording_of_screen: true }), "rejected");
  assertEquals(no({ looks_edited: true }), "rejected");
  assertEquals(no({ unsafe_or_inappropriate: true }), "rejected");
  assertEquals(no({ board_matches_station: "no", station_board_text: "THANE" }), "rejected");
  assertEquals(no({ features: [{ ...good.features[0], seen: false }] }), "rejected");
  assertEquals(no({ features: [{ ...good.features[0], confidence: "low" }] }), "rejected");
  // Gemini "seeing" something the visitor didn't claim, or that isn't needed, is ignored
  assertEquals(decide({ ...good, features: [{ ...good.features[0], key: "lift" }] }, ["accessible_toilet"], ctx).status,
    "rejected");
});

Deno.test("Gemini answers are validated, extra or broken fields are not trusted", () => {
  const ok = parseResult(JSON.stringify({ ...good, features: [...good.features,
    { key: "lift", seen: true, where: "x", at: "0:01", confidence: "high" }] }), ["accessible_toilet"]);
  assert(ok);
  assertEquals(ok.features.map((f) => f.key), ["accessible_toilet"]); // "lift" wasn't asked about
  assertEquals(parseResult("not json", ["accessible_toilet"]), null);
  assertEquals(parseResult(JSON.stringify({ ...good, looks_edited: "no" }), ["accessible_toilet"]), null);
  assertEquals(parseResult(JSON.stringify({ ...good, board_matches_station: "maybe" }), ["accessible_toilet"]), null);
});

Deno.test("prompt names the station and only the claimed facilities", () => {
  const p = buildPrompt(KALYAN, ["accessible_toilet"]);
  assert(p.includes("Kalyan") && p.includes("KYN") && p.includes("accessible_toilet"));
  assert(!p.includes("escalator"));
});

Deno.test("Gemini call: success, HTTP error and broken answer", async () => {
  const fake = (status: number, payload: unknown) => (() =>
    Promise.resolve(new Response(JSON.stringify(payload), { status }))) as unknown as typeof fetch;
  const args = { apiKey: "k", model: "m", videoBase64: "AAAA", mimeType: "video/webm", station: KALYAN,
    claimed: ["accessible_toilet"] };
  const answer = { candidates: [{ content: { parts: [{ text: JSON.stringify(good) }] } }],
    usageMetadata: { totalTokenCount: 9000 } };
  const ok = await checkVideo({ ...args, fetchFn: fake(200, answer) });
  assertEquals(ok.result?.features[0].key, "accessible_toilet");
  assertEquals(ok.tokens, 9000);
  assertEquals((await checkVideo({ ...args, fetchFn: fake(429, {}) })).result, null);
  const broken = { candidates: [{ content: { parts: [{ text: "{\"oops\":1}" }] } }] };
  assertEquals((await checkVideo({ ...args, fetchFn: fake(200, broken) })).result, null);
});
