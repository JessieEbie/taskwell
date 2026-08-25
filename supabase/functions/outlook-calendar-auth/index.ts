import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const CLIENT_ID = Deno.env.get("OUTLOOK_CLIENT_ID")!;
const CLIENT_SECRET = Deno.env.get("OUTLOOK_CLIENT_SECRET")!;
const TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token";

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

  const { action, code, code_verifier, redirect_uri, refresh_token, access_token, method, path, graph_body } = await req.json();

  // Microsoft Graph doesn't enable CORS for this app's registration (it's a
  // confidential/Web client, not a Single-page application), so the browser
  // can't call graph.microsoft.com directly — every such call is blocked at
  // the network level before any response even comes back ("Failed to
  // fetch"). Proxying it through this edge function sidesteps that entirely:
  // server-to-server calls aren't subject to browser CORS at all.
  if (action === "proxy") {
    if (!access_token || !path) return new Response("Missing access_token or path", { status: 400, headers: CORS });
    const r = await fetch(`https://graph.microsoft.com/v1.0/${path}`, {
      method: method || "GET",
      headers: { Authorization: `Bearer ${access_token}`, "Content-Type": "application/json" },
      body: graph_body ? JSON.stringify(graph_body) : undefined,
    });
    const text = await r.text();
    // A 204/304 (or any empty body) Response must have a null body, not "" —
    // Deno throws constructing one otherwise.
    return new Response(text || null, { status: r.status, headers: { ...CORS, "Content-Type": r.headers.get("Content-Type") || "application/json" } });
  }

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

  const r = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
  const result = await r.json();
  if (!r.ok) return new Response(JSON.stringify(result), { status: 400, headers: CORS });
  return new Response(JSON.stringify(result), { headers: { ...CORS, "Content-Type": "application/json" } });
});
