import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const targetUrl = new URL(req.url).searchParams.get("url");
  if (!targetUrl) return new Response("Missing url param", { status: 400, headers: CORS });

  try {
    const clean = targetUrl.replace(/^webcal:\/\//i, "https://");
    const res = await fetch(clean, { headers: { "User-Agent": "Taskwell/1.0" } });
    const text = await res.text();
    if (!text.includes("BEGIN:VCALENDAR")) throw new Error("Not a valid ICS feed");
    return new Response(text, { headers: { ...CORS, "Content-Type": "text/calendar; charset=utf-8" } });
  } catch (e) {
    return new Response(e.message, { status: 502, headers: CORS });
  }
});
