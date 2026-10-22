// POST /functions/v1/review-report   (admins only)
//   { action: "list" }                                   → pending reports with short-lived video links
//   { action: "approve", report_id, features: [...] }    → publish those facilities, delete the video
//   { action: "reject",  report_id, reason }             → reject, delete the video
import { VIDEO_FEATURES } from "../_shared/rules.ts";
import { adminClient, BUCKET, currentUser, isAdmin, istDate, preflight, reply, stations } from "../_shared/server.ts";

Deno.serve(async (req) => {
  const early = preflight(req);
  if (early) return early;

  const admin = adminClient();
  const user = await currentUser(req, admin);
  if (!user) return reply(req, { error: "Please sign in" }, 401);
  if (!(await isAdmin(admin, user))) return reply(req, { error: "Only reviewers can do this" }, 403);

  const body = await req.json().catch(() => ({})) as Record<string, unknown>;

  if (body.action === "list") {
    const { data, error } = await admin.from("reports")
      .select("id, station_id, claimed_features, suggested_features, distance_m, accuracy_m, duration_s, recorded_at, created_at, decided_by, reasons, gemini, video_path, user_id")
      .eq("status", "pending").order("created_at").limit(50);
    if (error) return reply(req, { error: "Couldn't load the queue" }, 500);
    const items = await Promise.all((data ?? []).map(async (r) => {
      // 10-minute link: enough to watch, useless if copied somewhere
      const { data: signed } = await admin.storage.from(BUCKET).createSignedUrl(r.video_path, 600);
      const { data: c } = await admin.from("contributors").select("approved_count, rejected_count")
        .eq("user_id", r.user_id).maybeSingle();
      const { user_id: _omit, video_path: _path, ...rest } = r;
      return {
        ...rest,
        station: stations[r.station_id]?.name ?? r.station_id,
        video_url: signed?.signedUrl ?? null,
        contributor: { approved: c?.approved_count ?? 0, rejected: c?.rejected_count ?? 0 },
      };
    }));
    return reply(req, { items, features: VIDEO_FEATURES });
  }

  if (body.action !== "approve" && body.action !== "reject") return reply(req, { error: "Unknown action" }, 400);
  if (typeof body.report_id !== "string") return reply(req, { error: "Missing report_id" }, 400);

  const { data: report } = await admin.from("reports")
    .select("id, user_id, station_id, claimed_features, recorded_at, video_path, gemini, status")
    .eq("id", body.report_id).maybeSingle();
  if (!report) return reply(req, { error: "Report not found" }, 404);
  if (report.status !== "pending") return reply(req, { error: "Already decided" }, 409);

  const reviewed = { reviewed_by: user.email, reviewed_at: new Date().toISOString(), decided_by: "admin" };

  if (body.action === "approve") {
    // Only facilities the visitor actually claimed can be published
    const features = (Array.isArray(body.features) ? body.features : [])
      .filter((f): f is string => typeof f === "string" && report.claimed_features.includes(f));
    if (!features.length) return reply(req, { error: "Pick at least one facility to publish" }, 400);
    const notes = new Map<string, string>(
      (report.gemini?.features ?? []).map((f: { key: string; where: string }) => [f.key, f.where]),
    );
    const { error } = await admin.from("facts").insert(features.map((f) => ({
      station_id: report.station_id, feature: f, note: notes.get(f) || null,
      seen_on: istDate(report.recorded_at ?? new Date().toISOString()), report_id: report.id,
    })));
    if (error) return reply(req, { error: "Couldn't publish" }, 500);
    await admin.from("reports").update({ status: "published", published_features: features, ...reviewed })
      .eq("id", report.id);
    await admin.rpc("bump_contributor", { p_user: report.user_id, p_approved: 1, p_rejected: 0 });
  } else {
    const reason = typeof body.reason === "string" && body.reason.trim() ? body.reason.trim().slice(0, 200)
      : "Not approved by a reviewer";
    await admin.from("reports").update({ status: "rejected", reasons: [reason], ...reviewed }).eq("id", report.id);
    await admin.rpc("bump_contributor", { p_user: report.user_id, p_approved: 0, p_rejected: 1 });
  }

  await admin.storage.from(BUCKET).remove([report.video_path]);
  return reply(req, { ok: true });
});
