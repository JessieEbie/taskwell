import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// This function's OWN project (the shared default backend) — used with the
// service_role key to write the directory table, bypassing RLS. The
// service_role key must only ever live here, as a server-side secret.
const HUB_SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const HUB_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  try {
    const { project_id, anon_key, access_token } = await req.json();
    if (!project_id || !anon_key || !access_token) {
      return new Response(JSON.stringify({ error: "Missing project_id, anon_key, or access_token" }), { status: 400, headers: CORS });
    }

    // Never trust a client-supplied email directly -- verify identity by
    // asking the SELF-HOSTED project itself who this access token belongs to.
    // Without this, anyone could register someone else's email pointing at
    // an attacker-controlled backend, silently redirecting that person into
    // it the next time they sign in.
    const projectUrl = `https://${project_id}.supabase.co`;
    const verifyRes = await fetch(`${projectUrl}/auth/v1/user`, {
      headers: { Authorization: `Bearer ${access_token}`, apikey: anon_key },
    });
    if (!verifyRes.ok) {
      return new Response(JSON.stringify({ error: "Could not verify identity with the provided backend" }), { status: 401, headers: CORS });
    }
    const verified = await verifyRes.json();
    const email = (verified?.email || "").toLowerCase();
    if (!email) {
      return new Response(JSON.stringify({ error: "No email on verified user" }), { status: 400, headers: CORS });
    }

    const hub = createClient(HUB_SUPABASE_URL, HUB_SERVICE_ROLE_KEY);
    const { error } = await hub.from("self_hosted_directory").upsert(
      { email, project_id, anon_key, updated_at: new Date().toISOString() },
      { onConflict: "email" }
    );
    if (error) {
      return new Response(JSON.stringify({ error: error.message }), { status: 500, headers: CORS });
    }
    return new Response(JSON.stringify({ ok: true }), { headers: { ...CORS, "Content-Type": "application/json" } });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: CORS });
  }
});
