import { findLessonByGroupAndDate, createLesson, setAttendance, getStudent } from "@/lib/db"
import { NextRequest } from "next/server"

export const dynamic = "force-dynamic"

export async function POST(req: NextRequest) {
  const { studentId, status } = await req.json()
  const student = await getStudent(studentId)
  if (!student) return Response.json({ error: "Student not found" }, { status: 404 })

  const today = new Date().toISOString().split("T")[0]
  let lesson = await findLessonByGroupAndDate(student.groupId, today)

  if (!lesson) {
    lesson = await createLesson(student.groupId, today, "Kunlik dars")
  }

  await setAttendance(studentId, lesson.id, status)

  return Response.json({ ok: true, lessonId: lesson.id, status })
}