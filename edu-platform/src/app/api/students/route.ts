import { getStudents, createStudent, deleteStudent, getGroups } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function GET(req: NextRequest) {
  const groupId = req.nextUrl.searchParams.get("groupId")
  let students = await getStudents(groupId ? parseInt(groupId) : undefined)
  // Teacher filter: only show students in their groups
  const teacherId = req.nextUrl.searchParams.get("teacherId")
  const role = req.nextUrl.searchParams.get("role")
  if (role === "teacher" && teacherId) {
    const groups = await getGroups()
    const teacherGroupIds = groups.filter((g: any) => g.teacherId === parseInt(teacherId)).map((g: any) => g.id)
    students = students.filter((s: any) => teacherGroupIds.includes(s.groupId))
  }
  return Response.json(students)
}

export async function POST(req: NextRequest) {
  const { name, phone, groupId, startDate } = await req.json()
  await createStudent(name, phone || "", groupId, startDate || "")
  return Response.json({ ok: true })
}

export async function DELETE(req: NextRequest) {
  const id = parseInt(req.nextUrl.searchParams.get("id")!)
  await deleteStudent(id)
  return Response.json({ ok: true })
}