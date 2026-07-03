import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const CLIENT_ID = Deno.env.get("GOOGLE_CLIENT_ID")!;
const CLIENT_SECRET = Deno.env.get("GOOGLE_CLIENT_SECRET")!;

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return new Response("Unauthorized", { status: 401, headers: CORS });

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } }
  );
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) {
    return new Response("Forbidden", { status: 403, headers: CORS });
  }

  const { action, code, code_verifier, redirect_uri, refresh_token } = await req.json();

  let body: Record<string, string>;
  if (action === "exchange") {
    body = { code, client_id: CLIENT_ID, client_secret: CLIENT_SECRET,
             redirect_uri, grant_type: "authorization_code", code_verifier };
  } else if (action === "refresh") {
    body = { refresh_token, client_id: CLIENT_ID, client_secret: CLIENT_SECRET,
             grant_type: "refresh_token" };
  } else {
    return new Response("Unknown action", { status: 400, headers: CORS });
  }

  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
  const result = await r.json();
  if (!r.ok) return new Response(JSON.stringify(result), { status: 400, headers: CORS });
  return new Response(JSON.stringify(result), { headers: { ...CORS, "Content-Type": "application/json" } });
});
