/**
 * Password hashing utilities — mirrors the PBKDF2 approach from
 * the Python app (app/api/classroom.py).
 */
import crypto from "crypto";

const ITERATIONS = 240_000;
const KEY_LENGTH = 32;
const DIGEST = "sha256";
const SALT_LENGTH = 16;

export function hashPassword(password: string, salt?: Buffer): string {
  const s = salt ?? crypto.randomBytes(SALT_LENGTH);
  const derived = crypto.pbkdf2Sync(password, s, ITERATIONS, KEY_LENGTH, DIGEST);
  return `${s.toString("hex")}:${derived.toString("hex")}`;
}

export function verifyPassword(password: string, stored: string): boolean {
  try {
    const [saltHex] = stored.split(":", 2);
    if (!saltHex) return false;
    const salt = Buffer.from(saltHex, "hex");
    const computed = hashPassword(password, salt);
    return crypto.timingSafeEqual(Buffer.from(computed), Buffer.from(stored));
  } catch {
    return false;
  }
}
