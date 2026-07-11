import postgres from "postgres"
import bcrypt from "bcryptjs"

const sql = postgres(process.env.DATABASE_URL!)

;(async () => {
  try { await sql`ALTER TABLE groups ADD COLUMN IF NOT EXISTS days TEXT DEFAULT ''` } catch {}
  try { await sql`ALTER TABLE groups ADD COLUMN IF NOT EXISTS subject TEXT DEFAULT ''` } catch {}
  try { await sql`ALTER TABLE groups ADD COLUMN IF NOT EXISTS teacher_id INT DEFAULT 0` } catch {}
  try { await sql`ALTER TABLE students ADD COLUMN IF NOT EXISTS start_date TEXT DEFAULT ''` } catch {}
})()

export async function getUsers() {
  const users = await sql`SELECT id, name, login, role, created_at as "createdAt" FROM users ORDER BY id`
  return users.map(u => ({ ...u, createdAt: u.createdAt?.toISOString?.() || u.createdAt }))
}
export async function getUserByLogin(login: string) {
  const [user] = await sql`SELECT * FROM users WHERE login = ${login}`
  return user || null
}
export async function getUserById(id: number) {
  const [user] = await sql`SELECT id, name, login, role, created_at as "createdAt" FROM users WHERE id = ${id}`
  return user || null
}
export async function createUser(name: string, login: string, password: string, role = "admin") {
  const [existing] = await sql`SELECT id FROM users WHERE login = ${login}`
  if (existing) return null
  const hash = bcrypt.hashSync(password, 10)
  const [user] = await sql`
    INSERT INTO users (name, login, password, role) VALUES (${name}, ${login}, ${hash}, ${role})
    RETURNING id, name, login, role, created_at as "createdAt"
  `
  return { ...user, createdAt: user.createdAt?.toISOString?.() || user.createdAt }
}
export async function updateUser(id: number, name: string, password?: string) {
  if (password) {
    const hash = bcrypt.hashSync(password, 10)
    const [user] = await sql`UPDATE users SET name = ${name}, password = ${hash} WHERE id = ${id} RETURNING id, name, login, role, created_at as "createdAt"`
    return user || null
  }
  const [user] = await sql`UPDATE users SET name = ${name} WHERE id = ${id} RETURNING id, name, login, role, created_at as "createdAt"`
  return user || null
}
export async function deleteUser(id: number) {
  if (id === 1) return false
  await sql`DELETE FROM users WHERE id = ${id}`
  return true
}

export async function getGroups() {
  const groups = await sql`
    SELECT g.*, COUNT(s.id)::int as "studentCount"
    FROM groups g LEFT JOIN students s ON s.group_id = g.id
    GROUP BY g.id ORDER BY g.id
  `
  return groups.map(g => ({
    id: g.id, name: g.name, description: g.description || "",
    pricePerLesson: g.price_per_lesson, days: g.days || "",
    subject: g.subject || "", teacherId: g.teacher_id || 0,
    studentCount: g.studentCount,
    createdAt: g.created_at?.toISOString?.() || g.created_at,
  }))
}
export async function getGroup(id: number) {
  const [g] = await sql`SELECT g.*, COUNT(s.id)::int as "studentCount" FROM groups g LEFT JOIN students s ON s.group_id = g.id WHERE g.id = ${id} GROUP BY g.id`
  if (!g) return null
  return { id: g.id, name: g.name, description: g.description || "", pricePerLesson: g.price_per_lesson, days: g.days || "", subject: g.subject || "", teacherId: g.teacher_id || 0, studentCount: g.studentCount, createdAt: g.created_at?.toISOString?.() || g.created_at }
}
export async function createGroup(name: string, description: string, pricePerLesson: number, days?: string, subject = "", teacherId = 0) {
  const [g] = await sql`
    INSERT INTO groups (name, description, price_per_lesson, days, subject, teacher_id) VALUES (${name}, ${description || ""}, ${pricePerLesson || 0}, ${days || ""}, ${subject}, ${teacherId})
    RETURNING *
  `
  return { id: g.id, name: g.name, description: g.description, pricePerLesson: g.price_per_lesson, days: g.days || "", subject: g.subject || "", teacherId: g.teacher_id || 0, createdAt: g.created_at?.toISOString?.() || g.created_at, studentCount: 0 }
}
export async function updateGroup(id: number, name: string, description: string, pricePerLesson: number, days?: string, subject?: string, teacherId?: number) {
  const [g] = await sql`
    UPDATE groups SET name = ${name}, description = ${description || ""}, price_per_lesson = ${pricePerLesson || 0}, days = ${days || ""}, subject = ${subject || ""}, teacher_id = ${teacherId || 0}
    WHERE id = ${id} RETURNING *
  `
  if (!g) return null
  return { id: g.id, name: g.name, description: g.description || "", pricePerLesson: g.price_per_lesson, days: g.days || "", subject: g.subject || "", teacherId: g.teacher_id || 0, createdAt: g.created_at?.toISOString?.() || g.created_at }
}
export async function deleteGroup(id: number) {
  await sql`DELETE FROM students WHERE group_id = ${id}`
  await sql`DELETE FROM groups WHERE id = ${id}`
}

export async function getStudents(groupId?: number) {
  const students = await sql`
    SELECT s.*, COALESCE(g.name, '') as "groupName"
    FROM students s LEFT JOIN groups g ON s.group_id = g.id
    ${groupId ? sql`WHERE s.group_id = ${groupId}` : sql``}
    ORDER BY s.id
  `
  return students.map(s => ({
    id: s.id, name: s.name, phone: s.phone || "", groupId: s.group_id,
    balance: s.balance, startDate: s.start_date || "",
    groupName: s.groupName,
    createdAt: s.created_at?.toISOString?.() || s.created_at,
  }))
}
export async function createStudent(name: string, phone: string, groupId: number, startDate = "") {
  const [s] = await sql`
    INSERT INTO students (name, phone, group_id, balance, start_date) VALUES (${name}, ${phone || ""}, ${groupId}, 0, ${startDate || new Date().toISOString().split("T")[0]})
    RETURNING *
  `
  return { id: s.id, name: s.name, phone: s.phone, groupId: s.group_id, balance: s.balance, startDate: s.start_date || "", createdAt: s.created_at?.toISOString?.() || s.created_at }
}
export async function deleteStudent(id: number) {
  await sql`DELETE FROM payments WHERE student_id = ${id}`
  await sql`DELETE FROM attendances WHERE student_id = ${id}`
  await sql`DELETE FROM students WHERE id = ${id}`
}
export async function getStudent(id: number) {
  const [s] = await sql`SELECT * FROM students WHERE id = ${id}`
  return s ? { ...s, groupId: s.group_id, startDate: s.start_date || "", createdAt: s.created_at?.toISOString?.() || s.created_at } : null
}

export async function getLessons() {
  const lessons = await sql`
    SELECT l.*, g.name as "groupName",
      COALESCE(a_counts.present, 0)::int as "presentCount",
      COALESCE(a_counts.absent, 0)::int as "absentCount",
      COALESCE(a_counts.total, 0)::int as "totalCount"
    FROM lessons l
    JOIN groups g ON l.group_id = g.id
    LEFT JOIN (
      SELECT lesson_id,
        COUNT(*)::int as total,
        COUNT(*) FILTER (WHERE status = 'present')::int as present,
        COUNT(*) FILTER (WHERE status = 'absent')::int as absent
      FROM attendances GROUP BY lesson_id
    ) a_counts ON a_counts.lesson_id = l.id
    ORDER BY l.created_at DESC
  `
  return lessons.map(l => ({
    id: l.id, groupId: l.group_id, date: l.date, topic: l.topic || "",
    groupName: l.groupName, presentCount: l.presentCount,
    absentCount: l.absentCount, totalCount: l.totalCount,
    createdAt: l.created_at?.toISOString?.() || l.created_at,
  }))
}
export async function createLesson(groupId: number, date: string, topic: string) {
  const [l] = await sql`INSERT INTO lessons (group_id, date, topic) VALUES (${groupId}, ${date}, ${topic || ""}) RETURNING *`
  return { id: l.id, groupId: l.group_id, date: l.date, topic: l.topic, createdAt: l.created_at?.toISOString?.() || l.created_at }
}
export async function findLessonByGroupAndDate(groupId: number, date: string) {
  const [l] = await sql`SELECT * FROM lessons WHERE group_id = ${groupId} AND date = ${date}`
  return l || null
}
export async function getTodayAttendance(groupId: number) {
  const today = new Date().toISOString().split("T")[0]
  const lesson = await sql`SELECT * FROM lessons WHERE group_id = ${groupId} AND date = ${today}`
  if (lesson.length === 0) return null
  const atts = await sql`SELECT a.*, ${today} as "lessonDate" FROM attendances a WHERE a.lesson_id = ${lesson[0].id}`
  return atts.map(a => ({ id: a.id, studentId: a.student_id, lessonId: a.lesson_id, status: a.status, date: a.lessonDate, createdAt: a.created_at?.toISOString?.() || a.created_at }))
}
export async function getMonthAttendances(month: string) {
  const rows = await sql`
    SELECT a.id, a.student_id as "studentId", a.lesson_id as "lessonId", a.status, l.date, a.created_at
    FROM attendances a JOIN lessons l ON a.lesson_id = l.id
    WHERE l.date LIKE ${month + "%"}
  `
  return rows.map(a => ({
    id: a.id, studentId: a.studentId, lessonId: a.lessonId, status: a.status,
    date: a.date, createdAt: a.created_at?.toISOString?.() || a.created_at,
  }))
}
export async function getStudentMonthAttendances(studentId: number, month: string) {
  const atts = await sql`
    SELECT a.*, l.date, l.id as "lessonId" FROM attendances a
    JOIN lessons l ON a.lesson_id = l.id
    WHERE a.student_id = ${studentId} AND l.date LIKE ${month + "%"} ORDER BY l.date
  `
  return atts.map((a, i) => ({
    id: a.id, studentId: a.student_id, lessonId: a.lessonId, status: a.status,
    date: a.date, lessonNumber: i + 1,
    createdAt: a.created_at?.toISOString?.() || a.created_at,
  }))
}
export async function setAttendance(studentId: number, lessonId: number, status: string) {
  const [existing] = await sql`SELECT id FROM attendances WHERE student_id = ${studentId} AND lesson_id = ${lessonId}`
  if (existing) {
    await sql`UPDATE attendances SET status = ${status} WHERE id = ${existing.id}`
  } else {
    await sql`INSERT INTO attendances (student_id, lesson_id, status) VALUES (${studentId}, ${lessonId}, ${status})`
  }
  if (status === "present" || status === "late") {
    const [student] = await sql`SELECT s.*, g.price_per_lesson FROM students s JOIN groups g ON s.group_id = g.id WHERE s.id = ${studentId}`
    if (student && student.price_per_lesson > 0) {
      const [lesson] = await sql`SELECT date FROM lessons WHERE id = ${lessonId}`
      await sql`UPDATE students SET balance = balance - ${student.price_per_lesson} WHERE id = ${studentId}`
      await sql`INSERT INTO payments (student_id, amount, type, note, date) VALUES (${studentId}, ${-student.price_per_lesson}, 'expense', ${`Dars: ${lesson?.date || ""}`}, ${lesson?.date || ""})`
    }
  }
}
export async function getPayments() {
  const payments = await sql`
    SELECT p.*, s.name as "studentName", COALESCE(g.name, '') as "groupName"
    FROM payments p JOIN students s ON p.student_id = s.id
    LEFT JOIN groups g ON s.group_id = g.id
    ORDER BY p.created_at DESC LIMIT 50
  `
  return payments.map(p => ({
    id: p.id, studentId: p.student_id, amount: p.amount, type: p.type,
    note: p.note || "", date: p.date, studentName: p.studentName, groupName: p.groupName,
    createdAt: p.created_at?.toISOString?.() || p.created_at,
  }))
}
export async function createPayment(studentId: number, amount: number, type: string, note: string, date: string) {
  const [p] = await sql`
    INSERT INTO payments (student_id, amount, type, note, date) VALUES (${studentId}, ${amount}, ${type}, ${note || ""}, ${date || new Date().toISOString().split("T")[0]})
    RETURNING *
  `
  if (type === "income") {
    await sql`UPDATE students SET balance = balance + ${amount} WHERE id = ${studentId}`
  } else {
    await sql`UPDATE students SET balance = balance - ${Math.abs(amount)} WHERE id = ${studentId}`
  }
  return { id: p.id, studentId: p.student_id, amount: p.amount, type: p.type, note: p.note, date: p.date, createdAt: p.created_at?.toISOString?.() || p.created_at }
}
export async function getStats() {
  const [counts] = await sql`
    SELECT (SELECT COUNT(*)::int FROM students) as students,
      (SELECT COUNT(*)::int FROM groups) as groups,
      (SELECT COUNT(*)::int FROM lessons) as lessons,
      (SELECT COALESCE(SUM(amount), 0)::int FROM payments WHERE type = 'income') as "totalPayments"
  `
  const recent = await sql`
    SELECT a.*, s.name as "studentName", g.name as "groupName", l.date
    FROM attendances a JOIN students s ON a.student_id = s.id
    JOIN lessons l ON a.lesson_id = l.id
    JOIN groups g ON l.group_id = g.id
    ORDER BY a.created_at DESC LIMIT 10
  `
  return {
    students: counts.students, groups: counts.groups, lessons: counts.lessons,
    totalPayments: counts.totalPayments,
    recentAttendance: recent.map(a => ({
      id: a.id, studentId: a.student_id, lessonId: a.lesson_id,
      status: a.status, studentName: a.studentName, groupName: a.groupName,
      date: a.date, createdAt: a.created_at?.toISOString?.() || a.created_at,
    })),
  }
}