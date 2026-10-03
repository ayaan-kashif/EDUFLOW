import crypto from "node:crypto";
import { cookies } from "next/headers";
import { getSupabaseAdmin } from "@/lib/supabase";
import { PortalUser } from "@/lib/types";

export const SESSION_COOKIE_NAME = "eduflow_session";
const SESSION_DAYS = 7;

export async function createSession(userId: string): Promise<string> {
  const token = crypto.randomBytes(32).toString("base64url");
  const tokenHash = crypto.createHash("sha256").update(token).digest("hex");
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const sessionId = crypto.randomUUID();

  const { error } = await getSupabaseAdmin().from("portal_sessions").insert({
    id: sessionId,
    user_id: userId,
    token_hash: tokenHash,
    expires_at: expiresAt,
  });
  if (error) throw new Error(error.message);

  return token;
}

export async function setSessionCookie(token: string): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_DAYS * 24 * 60 * 60,
  });
}

export async function clearSessionCookie(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
}

export async function getCurrentUser(): Promise<PortalUser | null> {
  try {
    const cookieStore = await cookies();
    const token = cookieStore.get(SESSION_COOKIE_NAME)?.value;
    if (!token) return null;

    const tokenHash = crypto.createHash("sha256").update(token).digest("hex");

    const admin = getSupabaseAdmin();
    const { data: session, error } = await admin.from("portal_sessions")
      .select("user_id, expires_at")
      .eq("token_hash", tokenHash)
      .maybeSingle();
    if (error) throw new Error(error.message);
    if (!session) return null;
    if (new Date(session.expires_at) < new Date()) {
      await admin.from("portal_sessions").delete().eq("token_hash", tokenHash);
      return null;
    }
    const { data: user, error: userError } = await admin.from("portal_users")
      .select("id, name, email, role, enrollment_code, created_at")
      .eq("id", session.user_id)
      .maybeSingle();
    if (userError) throw new Error(userError.message);
    return user as PortalUser | null;
  } catch (err) {
    console.error("Error getting current user:", err);
    return null;
  }
}

export async function deleteSession(token: string): Promise<void> {
  try {
    const tokenHash = crypto.createHash("sha256").update(token).digest("hex");

    const { error } = await getSupabaseAdmin().from("portal_sessions")
      .delete().eq("token_hash", tokenHash);
    if (error) throw new Error(error.message);
  } catch (err) {
    console.error("Error deleting session:", err);
  }
}
