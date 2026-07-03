import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  // Verify the caller is the allowed user
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

  const targetUrl = new URL(req.url).searchParams.get("url");
  if (!targetUrl) return new Response("Missing url param", { status: 400, headers: CORS });

  try {
    const params = new URL(req.url).searchParams;
    const clean = targetUrl.replace(/^webcal:\/\//i, "https://");
    const fetchHeaders: Record<string, string> = {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    };
    const username = params.get("username");
    const password = params.get("password");
    if (username) {
      fetchHeaders["Authorization"] = "Basic " + btoa(`${username}:${password ?? ""}`);
    }
    const res = await fetch(clean, { headers: fetchHeaders });
    const text = await res.text();
    if (!text.includes("BEGIN:VCALENDAR")) throw new Error("Not a valid ICS feed");
    return new Response(text, { headers: { ...CORS, "Content-Type": "text/calendar; charset=utf-8" } });
  } catch (e) {
    return new Response(e.message, { status: 502, headers: CORS });
  }
});
