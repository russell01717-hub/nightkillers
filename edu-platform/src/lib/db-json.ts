import fs from "fs"
import path from "path"
import bcrypt from "bcryptjs"

const dbPath = path.join(process.cwd(), "data.json")

interface StoredData {
  users: any[]
  groups: any[]
  students: any[]
  lessons: any[]
  attendances: any[]
  payments: any[]
}

let data: StoredData = { users: [], groups: [], students: [], lessons: [], attendances: [], payments: [] }
let ids = { users: 1, groups: 1, students: 1, lessons: 1, attendances: 1, payments: 1 }

function load() {
  if (fs.existsSync(dbPath)) {
    try {
      const raw = JSON.parse(fs.readFileSync(dbPath, "utf-8"))
      data = raw.data || raw
      ids = raw.ids || { users: data.users.length + 1, groups: data.groups.length + 1, students: data.students.length + 1, lessons: data.lessons.length + 1, attendances: data.attendances.length + 1, payments: data.payments.length + 1 }
    } catch { reset() }
  } else { reset() }
}

function reset() {
  data = { users: [], groups: [], students: [], lessons: [], attendances: [], payments: [] }
  ids = { users: 1, groups: 1, students: 1, lessons: 1, attendances: 1, payments: 1 }
  const ah = bcrypt.hashSync("admin123", 10)
  const sh = bcrypt.hashSync("4444", 10)
  const gh = bcrypt.hashSync("4444", 10)
  data.users.push({ id: nextId("users"), name: "Admin", login: "admin", password: ah, role: "admin", createdAt: new Date().toISOString() })
  data.users.push({ id: nextId("users"), name: "Sardor", login: "sardor", password: sh, role: "teacher", createdAt: new Date().toISOString() })
  data.users.push({ id: nextId("users"), name: "G'ayrat", login: "gayrat", password: gh, role: "teacher", createdAt: new Date().toISOString() })
  data.users.push({ id: nextId("users"), name: "Shoxali", login: "shoxali", password: gh, role: "teacher", createdAt: new Date().toISOString() })
  save()
}

function nextId(table: keyof StoredData) { return ids[table]++ }
function save() { fs.writeFileSync(dbPath, JSON.stringify({ data, ids }, null, 2)) }

export async function getUsers() { return data.users.map(u => { const { password, ...rest } = u; return rest }) }
export async function getUserByLogin(login: string) { return data.users.find(u => u.login === login) }
export async function getUserById(id: number) { return data.users.find(u => u.id === id) }
export async function createUser(name: string, login: string, password: string, role = "admin") {
  if (data.users.find(u => u.login === login)) return null
  const hash = bcrypt.hashSync(password, 10)
  const u = { id: nextId("users"), name, login, password: hash, role, createdAt: new Date().toISOString() }
  data.users.push(u); save()
  const { password: _, ...userData } = u
  return userData
}
export async function updateUser(id: number, name: string, password?: string) {
  const u = data.users.find(u => u.id === id)
  if (!u) return null
  if (name) u.name = name
  if (password) u.password = bcrypt.hashSync(password, 10)
  save()
  const { password: _, ...userData } = u
  return userData
}
export async function deleteUser(id: number) {
  if (id === 1) return false
  data.users = data.users.filter(u => u.id !== id)
  save()
  return true
}

// ─── Groups ─────────────────────────────────────────
export async function getGroups() {
  return data.groups.map(g => ({ ...g, studentCount: data.students.filter(s => s.groupId === g.id).length }))
}
export async function getGroup(id: number) {
  const g = data.groups.find(x => x.id === id)
  if (!g) return null
  return { ...g, studentCount: data.students.filter(s => s.groupId === g.id).length }
}
export async function createGroup(name: string, description: string, pricePerLesson: number, days?: string, subject = "", teacherId = 0) {
  const g = { id: nextId("groups"), name, description, pricePerLesson, days: days || "", subject, teacherId, createdAt: new Date().toISOString() }
  data.groups.push(g); save()
  return g
}
export async function updateGroup(id: number, name: string, description: string, pricePerLesson: number, days?: string, subject?: string, teacherId?: number) {
  const g = data.groups.find(x => x.id === id)
  if (!g) return null
  g.name = name; g.description = description; g.pricePerLesson = pricePerLesson
  if (days !== undefined) g.days = days
  if (subject !== undefined) g.subject = subject
  if (teacherId !== undefined) g.teacherId = teacherId
  save()
  return g
}
export async function deleteGroup(id: number) {
  data.groups = data.groups.filter(g => g.id !== id)
  data.students = data.students.filter(s => s.groupId !== id)
  save()
}

// ─── Students ───────────────────────────────────────
export async function getStudents(groupId?: number) {
  let rows = data.students.map(s => ({ ...s, groupName: data.groups.find(g => g.id === s.groupId)?.name || "" }))
  if (groupId) rows = rows.filter(s => s.groupId === groupId)
  return rows
}
export async function createStudent(name: string, phone: string, groupId: number, startDate = "") {
  const s = { id: nextId("students"), name, phone, groupId, balance: 0, startDate: startDate || new Date().toISOString().split("T")[0], createdAt: new Date().toISOString() }
  data.students.push(s); save()
  return s
}
export async function deleteStudent(id: number) {
  data.students = data.students.filter(s => s.id !== id)
  data.attendances = data.attendances.filter(a => a.studentId !== id)
  data.payments = data.payments.filter(p => p.studentId !== id)
  save()
}
export async function getStudent(id: number) { return data.students.find(s => s.id === id) }

// ─── Lessons ────────────────────────────────────────
export async function getLessons() {
  return data.lessons.map(l => {
    const g = data.groups.find(gr => gr.id === l.groupId)
    const atts = data.attendances.filter(a => a.lessonId === l.id)
    return { ...l, groupName: g?.name || "", presentCount: atts.filter(a => a.status === "present").length, absentCount: atts.filter(a => a.status === "absent").length, totalCount: atts.length }
  }).sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || ""))
}
export async function createLesson(groupId: number, date: string, topic: string) {
  const l = { id: nextId("lessons"), groupId, date, topic: topic || "", createdAt: new Date().toISOString() }
  data.lessons.push(l); save()
  return l
}
export async function findLessonByGroupAndDate(groupId: number, date: string) {
  return data.lessons.find(l => l.groupId === groupId && l.date === date) || null
}
export async function getTodayAttendance(groupId: number) {
  const today = new Date().toISOString().split("T")[0]
  const lesson = data.lessons.find(l => l.groupId === groupId && l.date === today)
  if (!lesson) return null
  return data.attendances.filter(a => a.lessonId === lesson.id).map(a => ({ ...a, lessonDate: today }))
}
export async function getMonthAttendances(month: string) {
  const monthLessons = data.lessons.filter(l => l.date?.startsWith(month))
  return data.attendances.filter(a => monthLessons.some(l => l.id === a.lessonId))
    .map(a => {
      const l = data.lessons.find(le => le.id === a.lessonId)
      return { id: a.id, studentId: a.studentId, lessonId: a.lessonId, status: a.status, date: l?.date || "", createdAt: a.createdAt }
    })
}
export async function getStudentMonthAttendances(studentId: number, month: string) {
  const monthLessons = data.lessons.filter(l => l.date?.startsWith(month))
  return data.attendances.filter(a => a.studentId === studentId && monthLessons.some(l => l.id === a.lessonId))
    .map(a => {
      const l = data.lessons.find(le => le.id === a.lessonId)
      return { ...a, date: l?.date || "", lessonNumber: monthLessons.filter(ml => ml.id <= a.lessonId).length }
    })
}
export async function setAttendance(studentId: number, lessonId: number, status: string) {
  const existing = data.attendances.find(a => a.studentId === studentId && a.lessonId === lessonId)
  if (existing) existing.status = status
  else data.attendances.push({ id: nextId("attendances"), studentId, lessonId, status, createdAt: new Date().toISOString() })
  if (status === "present" || status === "late") {
    const student = data.students.find(s => s.id === studentId)
    const group = data.groups.find(g => g.id === student?.groupId)
    if (student && group && group.pricePerLesson > 0) {
      student.balance -= group.pricePerLesson
      const lesson = data.lessons.find(l => l.id === lessonId)
      data.payments.push({ id: nextId("payments"), studentId, amount: -group.pricePerLesson, type: "expense", note: `Dars: ${lesson?.date || ""}`, date: lesson?.date || "", createdAt: new Date().toISOString() })
    }
  }
  save()
}
export async function getPayments() {
  return data.payments.map(p => {
    const s = data.students.find(st => st.id === p.studentId)
    const g = s ? data.groups.find(gr => gr.id === s.groupId) : null
    return { ...p, studentName: s?.name || "", groupName: g?.name || "" }
  }).sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || "")).slice(0, 50)
}
export async function createPayment(studentId: number, amount: number, type: string, note: string, date: string) {
  const p = { id: nextId("payments"), studentId, amount, type, note, date, createdAt: new Date().toISOString() }
  data.payments.push(p)
  const student = data.students.find(s => s.id === studentId)
  if (student) {
    if (type === "income") student.balance += amount
    else student.balance -= Math.abs(amount)
  }
  save()
  return p
}
export async function getStats() {
  const totalStudents = data.students.length
  const totalGroups = data.groups.length
  const totalLessons = data.lessons.length
  const totalPayments = data.payments.filter(p => p.type === "income").reduce((sum, p) => sum + p.amount, 0)
  const recentAttendance = data.attendances.map(a => {
    const s = data.students.find(st => st.id === a.studentId)
    const l = data.lessons.find(le => le.id === a.lessonId)
    const g = l ? data.groups.find(gr => gr.id === l.groupId) : null
    return { ...a, studentName: s?.name || "", groupName: g?.name || "", date: l?.date || "" }
  }).sort((a, b) => (b.createdAt || "").localeCompare(a.createdAt || "")).slice(0, 10)
  return { students: totalStudents, groups: totalGroups, lessons: totalLessons, totalPayments, recentAttendance }
}

load()