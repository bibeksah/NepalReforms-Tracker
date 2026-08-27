import { createClient } from "@supabase/supabase-js"

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  process.env.SUPABASE_URL ||
  "https://nokrhvgrfcletinhsalt.supabase.co"

const supabaseKey =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ||
  process.env.SUPABASE_ANON_KEY ||
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5va3JodmdyZmNsZXRpbmhzYWx0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc1OTI0NzMsImV4cCI6MjA3MzE2ODQ3M30.1TUEt1q-JTXHAHZINCavbnH_X0TxyDu49Q2QzdogZmE"

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: false,
    autoRefreshToken: false,
  },
})
