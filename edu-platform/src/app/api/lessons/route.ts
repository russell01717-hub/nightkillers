import { getLessons, createLesson, getGroups } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function GET(req: NextRequest) {
  let lessons = await getLessons()
  const teacherId = req.nextUrl.searchParams.get("teacherId")
  const role = req.nextUrl.searchParams.get("role")
  if (role === "teacher" && teacherId) {
    const groups = await getGroups()
    const teacherGroupIds = groups.filter((g: any) => g.teacherId === parseInt(teacherId)).map((g: any) => g.id)
    lessons = lessons.filter((l: any) => teacherGroupIds.includes(l.groupId))
  }
  return Response.json(lessons)
}

export async function POST(req: NextRequest) {
  const { groupId, date, topic } = await req.json()
  const lesson = await createLesson(groupId, date, topic || "")
  return Response.json({ id: lesson.id })
}