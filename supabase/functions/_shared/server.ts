// Plumbing shared by the Edge Functions: CORS, JSON replies, the service-role client,
// the signed-in user, settings and stations.
import { createClient, type SupabaseClient, type User } from "npm:@supabase/supabase-js@2.117.3";
import stationsJson from "./stations.json" with { type: "json" };
import type { Limits, Station } from "./rules.ts";

export const BUCKET = "report-videos";
export const stations = stationsJson as Record<string, Station>;

// Only the Rail Club site may call these functions from a browser.
const ORIGINS = (Deno.env.get("ALLOWED_ORIGINS") ?? "https://railclub.github.io,http://localhost:8000")
  .split(",").map((s) => s.trim()).filter(Boolean);

function cors(req: Request): Record<string, string> {
  const origin = req.headers.get("origin") ?? "";
  return {
    "access-control-allow-origin": ORIGINS.includes(origin) ? origin : ORIGINS[0],
    "access-control-allow-headers": "authorization, x-client-info, apikey, content-type",
    "access-control-allow-methods": "POST, OPTIONS",
    "vary": "origin",
  };
}

export function preflight(req: Request): Response | null {
  if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });
  if (req.method !== "POST") return reply(req, { error: "Use POST" }, 405);
  return null;
}

export function reply(req: Request, body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { ...cors(req), "content-type": "application/json" } });
}

export function adminClient(): SupabaseClient {
  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) throw new Error("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set");
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

/** The signed-in visitor, checked with Supabase Auth (never trust a user id sent in the body). */
export async function currentUser(req: Request, admin: SupabaseClient): Promise<User | null> {
  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  if (!token) return null;
  const { data, error } = await admin.auth.getUser(token);
  return error ? null : data.user;
}

export async function loadLimits(admin: SupabaseClient): Promise<Limits> {
  const { data, error } = await admin.from("settings").select("value").eq("key", "limits").single();
  if (error || !data) throw new Error("settings.limits missing");
  return data.value as Limits;
}

export async function isAdmin(admin: SupabaseClient, user: User): Promise<boolean> {
  if (!user.email || !user.email_confirmed_at) return false;
  const { data } = await admin.from("admins").select("email").eq("email", user.email.toLowerCase()).maybeSingle();
  return !!data;
}

/** "Today" and "this month" in India, as UTC timestamps for queries. */
export function istStartOf(unit: "day" | "month", now = new Date()): string {
  const ist = new Date(now.getTime() + 5.5 * 3600_000);
  const start = Date.UTC(ist.getUTCFullYear(), ist.getUTCMonth(), unit === "day" ? ist.getUTCDate() : 1);
  return new Date(start - 5.5 * 3600_000).toISOString();
}

export function istDate(iso: string): string {
  return new Date(Date.parse(iso) + 5.5 * 3600_000).toISOString().slice(0, 10);
}
