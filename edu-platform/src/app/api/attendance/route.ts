import { setAttendance, getMonthAttendances } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function GET(req: NextRequest) {
  const month = req.nextUrl.searchParams.get("month")
  if (!month) return Response.json([])
  return Response.json(await getMonthAttendances(month))
}

export async function POST(req: NextRequest) {
  const { attendances } = await req.json()

  for (const a of attendances) {
    await setAttendance(a.studentId, a.lessonId, a.status)
  }

  return Response.json({ ok: true })
}
