import { getUsers, createUser, updateUser, deleteUser, getUserById } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function GET() {
  return Response.json(await getUsers())
}

export async function POST(req: NextRequest) {
  const { name, login, password, role } = await req.json()
  const user = await createUser(name, login, password, role || "admin")
  if (!user) return Response.json({ error: "Bu login band" }, { status: 400 })
  return Response.json(user)
}

export async function PUT(req: NextRequest) {
  const { id, name, password } = await req.json()
  const user = await updateUser(id, name, password)
  if (!user) return Response.json({ error: "Foydalanuvchi topilmadi" }, { status: 404 })
  return Response.json(user)
}

export async function DELETE(req: NextRequest) {
  const id = parseInt(req.nextUrl.searchParams.get("id")!)
  const ok = await deleteUser(id)
  if (!ok) return Response.json({ error: "Admin o'chirilmaydi" }, { status: 400 })
  return Response.json({ ok: true })
}
