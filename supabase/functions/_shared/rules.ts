// The gates a visitor report goes through, and the final decision.
// Pure functions only (no network, no database) so every rule can be unit-tested.
// Order matters: everything here except decide() runs BEFORE Gemini, so a report that
// fails a free check never costs anything.

export type Limits = {
  per_user_per_day: number;
  per_station_per_day: number;
  min_seconds: number;
  max_seconds: number;
  max_bytes: number;
  radius_m: number;
  radius_overrides_m: Record<string, number>;
  max_accuracy_m: number;
  max_upload_age_min: number;
  trust_after_approved: number;
  distrust_after_rejected: number;
  confirmed_reports_needed: number;
  confirmed_within_days: number;
  pending_keep_days: number;
  monthly_gemini_calls: number;
};

export type Station = {
  name: string;
  code: string;
  division: string;
  aliases: string[];
  official_yes: string[];
  lat?: number;
  lon?: number;
};

// Facilities a short video can actually show. Booking and human-assistance services
// can't be seen on camera, so visitors can't claim them.
export const VIDEO_FEATURES: Record<string, string> = {
  lift: "Lift / elevator for passengers",
  escalator: "Escalator",
  ramp_entry: "Ramp at the station's main entrance",
  ramp_second: "Ramp at a second entrance",
  ramp_fob: "Ramp on a foot over bridge or subway between platforms",
  accessible_toilet: "Toilet marked for persons with disabilities (Divyangjan)",
  water_booth: "Low-height drinking water booth or tap for wheelchair users",
  parking: "Parking space marked for persons with disabilities",
  help_booth: "Help / enquiry booth ('May I help you')",
  low_counter: "Low-height ticket counter",
  tactile_path: "Tactile paving (raised yellow tiles) for blind passengers",
  braille_signage: "Braille signage",
  braille_map: "Audio or Braille map of the station",
  wheelchair: "Wheelchair available for passengers",
  battery_car: "Battery-operated car for passengers",
  boarding_ramp: "Portable ramp for boarding coaches",
};

export type Outcome =
  | { ok: true }
  | { ok: false; status: "rejected" | "not_needed" | "pending"; gate: string; reason: string };

const pass: Outcome = { ok: true };
const stop = (status: "rejected" | "not_needed" | "pending", gate: string, reason: string): Outcome =>
  ({ ok: false, status, gate, reason });

// ---------- request ----------

export type SubmitInput = {
  station_id: string;
  features: string[];
  lat: number;
  lon: number;
  accuracy_m: number;
  duration_s: number;
  recorded_at: string;
  video_path: string;
  consent_version: string;
};

export function parseInput(body: unknown, userId: string): SubmitInput | string {
  if (!body || typeof body !== "object") return "Missing request body";
  const b = body as Record<string, unknown>;
  const num = (k: string) => (typeof b[k] === "number" && Number.isFinite(b[k]) ? (b[k] as number) : NaN);
  const str = (k: string) => (typeof b[k] === "string" ? (b[k] as string) : "");
  const input: SubmitInput = {
    station_id: str("station_id"),
    features: Array.isArray(b.features) ? [...new Set(b.features.filter((f) => typeof f === "string"))] as string[] : [],
    lat: num("lat"),
    lon: num("lon"),
    accuracy_m: num("accuracy_m"),
    duration_s: num("duration_s"),
    recorded_at: str("recorded_at"),
    video_path: str("video_path"),
    consent_version: str("consent_version"),
  };
  if (!/^[a-z0-9-]{1,80}$/.test(input.station_id)) return "Unknown station";
  if (!input.features.length || input.features.length > 8) return "Tick between 1 and 8 facilities";
  if (input.features.some((f) => !(f in VIDEO_FEATURES))) return "Unknown facility";
  if (Math.abs(input.lat) > 90 || Math.abs(input.lon) > 180 || Number.isNaN(input.lat) || Number.isNaN(input.lon)) {
    return "Location missing";
  }
  if (!(input.accuracy_m >= 0)) return "Location accuracy missing";
  if (Number.isNaN(Date.parse(input.recorded_at))) return "Recording time missing";
  // Only a file in the visitor's own folder, with a plain file name: no "../" tricks
  if (!new RegExp(`^${userId}/[A-Za-z0-9-]{8,64}\\.(webm|mp4)$`).test(input.video_path)) return "Invalid video path";
  if (!input.consent_version) return "Consent missing";
  return input;
}

// ---------- gates before Gemini (all free) ----------

export function gateContributor(c: { blocked: boolean } | null): Outcome {
  return c?.blocked ? stop("rejected", "contributor", "Your account can't send reports right now") : pass;
}

export function gateLimits(userToday: number, stationToday: number, limits: Limits): Outcome {
  if (userToday >= limits.per_user_per_day) {
    return stop("rejected", "limits", `You've sent ${limits.per_user_per_day} reports today. Please try again tomorrow`);
  }
  if (stationToday >= limits.per_station_per_day) {
    return stop("rejected", "limits", "This station has had enough reports today. Please try again tomorrow");
  }
  return pass;
}

export function distanceM(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371000, toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat), dLon = toRad(bLon - aLon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export type LocationCheck = Outcome & { distance_m: number | null; has_coords: boolean };

export function gateLocation(stationId: string, station: Station, lat: number, lon: number, accuracy: number,
  limits: Limits): LocationCheck {
  if (accuracy > limits.max_accuracy_m) {
    return { ...stop("rejected", "location", "Your location wasn't precise enough. Step outside the building and try again"),
      distance_m: null, has_coords: station.lat !== undefined };
  }
  if (station.lat === undefined || station.lon === undefined) {
    // We can't check, so this report can only ever be published by a reviewer (see decide()).
    return { ...pass, distance_m: null, has_coords: false };
  }
  const d = distanceM(lat, lon, station.lat, station.lon);
  const radius = limits.radius_overrides_m[stationId] ?? limits.radius_m;
  // GPS error counts in the visitor's favour, but only up to the accuracy limit
  if (d - Math.min(accuracy, limits.max_accuracy_m) > radius) {
    return { ...stop("rejected", "location", `You don't seem to be at ${station.name}`), distance_m: Math.round(d), has_coords: true };
  }
  return { ...pass, distance_m: Math.round(d), has_coords: true };
}

export function gateRecording(durationS: number, recordedAt: string, uploadedAt: string, now: Date,
  limits: Limits): Outcome {
  if (!(durationS >= limits.min_seconds - 1 && durationS <= limits.max_seconds + 2)) {
    return stop("rejected", "recording", `Videos must be ${limits.min_seconds}–${limits.max_seconds} seconds long`);
  }
  const maxAge = limits.max_upload_age_min * 60_000;
  const recorded = Date.parse(recordedAt), uploaded = Date.parse(uploadedAt);
  if (Number.isNaN(uploaded) || now.getTime() - uploaded > maxAge || now.getTime() - recorded > maxAge + 120_000) {
    return stop("rejected", "recording", "This video wasn't recorded just now. Please record it again at the station");
  }
  if (recorded > now.getTime() + 120_000) return stop("rejected", "recording", "The recording time looks wrong");
  return pass;
}

export function gateFile(size: number, mimetype: string, limits: Limits): Outcome {
  if (!size) return stop("rejected", "file", "The video didn't upload. Please try again");
  if (size > limits.max_bytes) return stop("rejected", "file", "The video is too large");
  if (!/^video\/(webm|mp4)\b/.test(mimetype)) return stop("rejected", "file", "That isn't a supported video");
  return pass;
}

export function gateDuplicate(alreadySeen: boolean): Outcome {
  return alreadySeen ? stop("rejected", "duplicate", "This video was already sent") : pass;
}

/** Facilities the visitor ticked that still need confirming: not in the official data, and not
 * already confirmed by enough recent visitor reports. */
export function stillNeeded(claimed: string[], station: Station, recentFactCounts: Record<string, number>,
  limits: Limits): string[] {
  return claimed.filter((f) =>
    !station.official_yes.includes(f) && (recentFactCounts[f] ?? 0) < limits.confirmed_reports_needed
  );
}

export function gateNeeded(needed: string[]): Outcome {
  return needed.length ? pass
    : stop("not_needed", "needed", "Thank you! Everything you filmed is already confirmed for this station");
}

export function gateBudget(geminiCallsThisMonth: number, limits: Limits): Outcome {
  // Over budget: nothing is lost, the report just waits for a human instead of the AI
  return geminiCallsThisMonth >= limits.monthly_gemini_calls
    ? stop("pending", "budget", "Waiting for a reviewer (automatic checks are paused for this month)")
    : pass;
}

// ---------- after Gemini: the decision is made by these rules, not by the model ----------

export type GeminiFeature = { key: string; seen: boolean; where: string; at: string; confidence: "high" | "medium" | "low" };

export type GeminiResult = {
  is_railway_station: boolean;
  inside_station_premises: boolean;
  station_board_visible: boolean;
  station_board_text: string;
  board_matches_station: "yes" | "no" | "not_visible";
  is_screen_or_recording_of_screen: boolean;
  looks_edited: boolean;
  unsafe_or_inappropriate: boolean;
  features: GeminiFeature[];
  notes: string;
};

export type Decision = {
  status: "rejected" | "pending" | "published";
  reasons: string[];
  confirmed: GeminiFeature[]; // what can be published (now, or by a reviewer)
};

export function decide(g: GeminiResult, needed: string[], ctx: {
  has_coords: boolean;
  approved: number;
  rejected: number;
  limits: Limits;
  stationName: string;
}): Decision {
  const reject = (reason: string): Decision => ({ status: "rejected", reasons: [reason], confirmed: [] });
  if (g.is_screen_or_recording_of_screen) return reject("This looks like a recording of a screen");
  if (g.looks_edited) return reject("This video looks edited");
  if (g.unsafe_or_inappropriate) return reject("This video can't be accepted");
  if (!g.is_railway_station) return reject("This doesn't look like a railway station");
  if (!g.inside_station_premises) return reject("This seems to be filmed outside the station");
  if (g.board_matches_station === "no") {
    return reject(`The station board shows a different station${g.station_board_text ? ` (${g.station_board_text})` : ""}`);
  }

  // Only facilities the visitor ticked, that are still needed, that Gemini saw with some confidence
  const byKey = new Map<string, GeminiFeature>();
  for (const f of g.features) {
    if (f.seen && needed.includes(f.key) && f.confidence !== "low" && !byKey.has(f.key)) byKey.set(f.key, f);
  }
  const confirmed = [...byKey.values()];
  if (!confirmed.length) return reject("We couldn't see the facilities you ticked in the video");

  const review: string[] = [];
  if (!ctx.has_coords) review.push(`We can't check locations at ${ctx.stationName} automatically yet`);
  if (ctx.approved < ctx.limits.trust_after_approved) review.push("New contributors' reports are checked by a person");
  if (ctx.rejected >= ctx.limits.distrust_after_rejected) review.push("Checked by a person");
  if (confirmed.some((f) => f.confidence !== "high")) review.push("Some facilities weren't fully clear");
  return review.length
    ? { status: "pending", reasons: review, confirmed }
    : { status: "published", reasons: [], confirmed };
}
