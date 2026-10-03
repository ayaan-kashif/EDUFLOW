import crypto from "node:crypto";
import { cookies } from "next/headers";
import { getDb } from "@/lib/db";
import { getSupabaseAdmin, isSupabaseReady } from "@/lib/supabase";
import { PortalUser } from "@/lib/types";

export const SESSION_COOKIE_NAME = "eduflow_session";
const SESSION_DAYS = 7;

export async function createSession(userId: string): Promise<string> {
  const token = crypto.randomBytes(32).toString("base64url");
  const tokenHash = crypto.createHash("sha256").update(token).digest("hex");
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const sessionId = crypto.randomUUID();

  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    await supabase.from("portal_sessions").insert({
      id: sessionId,
      user_id: userId,
      token_hash: tokenHash,
      expires_at: expiresAt,
    });
  }

  const db = getDb();
  const stmt = db.prepare(`
    INSERT INTO portal_sessions (id, user_id, token_hash, expires_at)
    VALUES (?, ?, ?, ?)
  `);
  stmt.run(sessionId, userId, tokenHash, expiresAt);

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

    if (await isSupabaseReady()) {
      const supabase = getSupabaseAdmin();
      const { data: session } = await supabase
        .from("portal_sessions")
        .select("expires_at, user:portal_users!portal_sessions_user_id_fkey(id, name, email, role, enrollment_code, created_at)")
        .eq("token_hash", tokenHash)
        .single();

      if (session) {
        if (new Date(session.expires_at) < new Date()) {
          await supabase.from("portal_sessions").delete().eq("token_hash", tokenHash);
          return null;
        }
        return (session as any).user;
      }
    }

    const db = getDb();
    const stmt = db.prepare(`
      SELECT u.id, u.name, u.email, u.role, u.enrollment_code, u.created_at, s.expires_at
      FROM portal_sessions s
      JOIN portal_users u ON s.user_id = u.id
      WHERE s.token_hash = ?
    `);

    const row = stmt.get(tokenHash) as any;
    if (!row) return null;

    if (new Date(row.expires_at) < new Date()) {
      db.prepare("DELETE FROM portal_sessions WHERE token_hash = ?").run(tokenHash);
      return null;
    }

    return {
      id: row.id,
      name: row.name,
      email: row.email,
      role: row.role,
      enrollment_code: row.enrollment_code,
      created_at: row.created_at,
    };
  } catch (err) {
    console.error("Error getting current user:", err);
    return null;
  }
}

export async function deleteSession(token: string): Promise<void> {
  try {
    const tokenHash = crypto.createHash("sha256").update(token).digest("hex");

    if (await isSupabaseReady()) {
      const supabase = getSupabaseAdmin();
      await supabase.from("portal_sessions").delete().eq("token_hash", tokenHash);
    }

    const db = getDb();
    db.prepare("DELETE FROM portal_sessions WHERE token_hash = ?").run(tokenHash);
  } catch (err) {
    console.error("Error deleting session:", err);
  }
}
