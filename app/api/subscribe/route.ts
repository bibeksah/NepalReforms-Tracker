import { NextRequest, NextResponse } from "next/server"
import { supabase } from "@/lib/supabase"

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export async function POST(req: NextRequest) {
  try {
    const body = await req.json().catch(() => ({}))
    const { email, source = "homepage", agenda_id = null } = body

    if (!email || typeof email !== "string" || !EMAIL_REGEX.test(email.trim())) {
      return NextResponse.json(
        { success: false, error: "Please provide a valid email address." },
        { status: 400 }
      )
    }

    const cleanEmail = email.trim().toLowerCase()
    const cleanSource = typeof source === "string" ? source.trim() : "homepage"
    const cleanAgendaId = agenda_id ? String(agenda_id).trim() : null

    // Insert into tracker_subscribers in Supabase
    const { data, error } = await supabase
      .from("tracker_subscribers")
      .insert({
        email: cleanEmail,
        source: cleanSource,
        agenda_id: cleanAgendaId,
      })
      .select("id, created_at")
      .single()

    if (error) {
      // Handle unique constraint violation (already subscribed)
      if (error.code === "23505") {
        return NextResponse.json({
          success: true,
          alreadySubscribed: true,
          message: "You are already registered on the early access list!",
        })
      }

      console.error("Supabase tracker_subscribers insert error:", error)
      return NextResponse.json(
        { success: false, error: "Failed to record subscription. Please try again." },
        { status: 500 }
      )
    }

    return NextResponse.json({
      success: true,
      data,
      message: "Successfully added to the Tracker early access list!",
    })
  } catch (err) {
    console.error("Tracker subscription endpoint error:", err)
    return NextResponse.json(
      { success: false, error: "An unexpected error occurred." },
      { status: 500 }
    )
  }
}
