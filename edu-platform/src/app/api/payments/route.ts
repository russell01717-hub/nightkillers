import { getPayments, createPayment } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function GET() {
  return Response.json(await getPayments())
}

export async function POST(req: NextRequest) {
  const { studentId, amount, note, date } = await req.json()
  await createPayment(studentId, amount, "income", note || "", date)
  return Response.json({ ok: true })
}
