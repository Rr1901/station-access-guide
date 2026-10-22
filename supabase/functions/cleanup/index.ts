// POST /functions/v1/cleanup   (run daily by Supabase Cron; deploy with --no-verify-jwt)
// Deletes videos that should no longer exist:
//   * reports still waiting for a reviewer after `pending_keep_days` → marked "expired"
//   * uploads that never became a report (page closed mid-way) after a day
// Protected by a shared secret header instead of a user login.
import { adminClient, BUCKET, loadLimits } from "../_shared/server.ts";

Deno.serve(async (req) => {
  const secret = Deno.env.get("CRON_SECRET");
  if (!secret || req.headers.get("x-cron-secret") !== secret) return new Response("Forbidden", { status: 403 });

  const admin = adminClient();
  const limits = await loadLimits(admin);
  const cutoff = new Date(Date.now() - limits.pending_keep_days * 86_400_000).toISOString();

  const { data: stale } = await admin.from("reports").select("id, video_path")
    .eq("status", "pending").lt("created_at", cutoff).limit(500);
  const expiredPaths = (stale ?? []).map((r) => r.video_path).filter(Boolean) as string[];
  if (stale?.length) {
    await admin.from("reports").update({ status: "expired", reasons: ["Not reviewed in time"] })
      .in("id", stale.map((r) => r.id));
  }

  const { data: orphans } = await admin.rpc("orphan_videos", { p_older_than: "1 day" });
  const orphanPaths = ((orphans ?? []) as { name: string }[]).map((o) => o.name);

  const paths = [...expiredPaths, ...orphanPaths];
  for (let i = 0; i < paths.length; i += 100) await admin.storage.from(BUCKET).remove(paths.slice(i, i + 100));

  return new Response(JSON.stringify({ expired: expiredPaths.length, orphans: orphanPaths.length }),
    { headers: { "content-type": "application/json" } });
});
