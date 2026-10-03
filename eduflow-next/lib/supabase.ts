import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  process.env.SUPABASE_URL ||
  "";

const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  process.env.SUPABASE_PUBLISHABLE_KEY ||
  "";

const supabaseSecretKey =
  process.env.SUPABASE_SECRET_KEY ||
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  "";

let clientInstance: SupabaseClient | null = null;
let adminInstance: SupabaseClient | null = null;

let supabaseReadyCache: boolean | null = null;
let lastCheckTime = 0;

/**
 * Public client for client components and standard operations.
 */
export function getSupabaseClient(): SupabaseClient {
  if (!clientInstance) {
    clientInstance = createClient(supabaseUrl, supabaseAnonKey, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
      },
    });
  }
  return clientInstance;
}

/**
 * Privileged admin client for server-side API routes.
 */
export function getSupabaseAdmin(): SupabaseClient {
  if (!/^https:\/\/[^/]+\.supabase\.co$/.test(supabaseUrl)) {
    throw new Error("SUPABASE_URL must be the project URL");
  }
  if (!/^(sb_secret_[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)$/.test(supabaseSecretKey)) {
    throw new Error("SUPABASE_SECRET_KEY must be a complete server-side key");
  }
  if (!adminInstance) {
    adminInstance = createClient(supabaseUrl, supabaseSecretKey, {
      auth: {
        persistSession: false,
        autoRefreshToken: false,
      },
    });
  }
  return adminInstance;
}

/**
 * Determines whether Supabase tables have been created and are ready for queries.
 */
export async function isSupabaseReady(): Promise<boolean> {
  const now = Date.now();
  if (supabaseReadyCache !== null && now - lastCheckTime < 10000) {
    return supabaseReadyCache;
  }
  try {
    const admin = getSupabaseAdmin();
    const { error } = await admin.from("portal_users").select("id").limit(1);
    supabaseReadyCache = !error;
    lastCheckTime = now;
    return supabaseReadyCache;
  } catch {
    supabaseReadyCache = false;
    lastCheckTime = now;
    return false;
  }
}

/**
 * Check connectivity to Supabase
 */
export async function checkSupabaseHealth(): Promise<{
  connected: boolean;
  tablesReady: boolean;
  error?: string;
}> {
  try {
    const admin = getSupabaseAdmin();
    const { error } = await admin.from("portal_users").select("id").limit(1);
    return {
      connected: !error,
      tablesReady: !error,
      ...(error ? { error: error.message } : {}),
    };
  } catch (err) {
    return {
      connected: false,
      tablesReady: false,
      error: err instanceof Error ? err.message : "Supabase unavailable",
    };
  }
}
