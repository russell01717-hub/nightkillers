"use client"
import { useEffect, useState } from "react"

const STATUS_CYCLE = ["present", "absent", "late"] as const

export default function AttendancePage() {
  const [groups, setGroups] = useState<any[]>([])
  const [selectedGroup, setSelectedGroup] = useState("")
  const [date, setDate] = useState(new Date().toISOString().split("T")[0])
  const [topic, setTopic] = useState("")
  const [step, setStep] = useState("select")
  const [students, setStudents] = useState<any[]>([])
  const [attendances, setAttendances] = useState<Record<number, string>>({})
  const [currentLessonId, setCurrentLessonId] = useState<number | null>(null)
  const [msg, setMsg] = useState("")
  const [lessonNumber, setLessonNumber] = useState(0)
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    try { setUser(JSON.parse(atob(localStorage.getItem("token") || ""))) } catch {}
  }, [])

  const teacherParams = user?.role === "teacher" ? `?role=teacher&teacherId=${user.id}` : ""
  useEffect(() => { fetch(`/api/groups${teacherParams}`).then(r => r.json()).then(setGroups) }, [teacherParams])

  const group = groups.find(g => g.id === parseInt(selectedGroup))

  async function startLesson() {
    if (!selectedGroup || !date) return
    const res = await fetch("/api/lessons", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groupId: parseInt(selectedGroup), date, topic }) })
    const lesson = await res.json()
    setCurrentLessonId(lesson.id)
    const res2 = await fetch(`/api/students?groupId=${selectedGroup}`)
    const sts = await res2.json()
    setStudents(sts)
    const att: Record<number, string> = {}
    sts.forEach((s: any) => { att[s.id] = "present" })
    setAttendances(att); setStep("taking"); setMsg("")
    // Lesson number
    const month = date.substring(0, 7)
    const res3 = await fetch("/api/lessons")
    const allLessons = await res3.json()
    const monthLessons = allLessons.filter((l: any) => l.groupId === parseInt(selectedGroup) && l.date?.startsWith(month))
    setLessonNumber(monthLessons.length)
  }

  function toggleStatus(id: number) {
    setAttendances(prev => {
      const cur = prev[id] || "present"
      const idx = STATUS_CYCLE.indexOf(cur as any)
      const next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length]
      return { ...prev, [id]: next }
    })
  }

  async function saveAttendance() {
    if (!currentLessonId) return
    const data = Object.entries(attendances).map(([sid, status]) => ({ studentId: parseInt(sid), lessonId: currentLessonId, status }))
    await fetch("/api/attendance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ attendances: data }) })
    setMsg("Davomat saqlandi!")
    setTimeout(() => { setStep("select"); setMsg(""); setCurrentLessonId(null); setStudents([]); setLessonNumber(0) }, 1000)
  }

  const statusConfig: Record<string, any> = {
    present: { label: "Keldi", icon: "fa-check-circle", bg: "#d1fae5", border: "#6ee7b7", color: "#065f46" },
    late: { label: "Kechikdi", icon: "fa-clock", bg: "#fef3c7", border: "#fcd34d", color: "#92400e" },
    absent: { label: "Kelmadi", icon: "fa-times-circle", bg: "#fee2e2", border: "#fca5a5", color: "#991b1b" },
  }

  return (
    <div className="animate-fadeIn">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Davomat</h1>
        <p className="text-sm text-gray-400"><i className="fas fa-check-circle mr-1" style={{ color: "var(--theme-primary)" }} />Darsga kelgan/kelmaganlarni belgilang</p>
      </div>
      {step === "select" ? (
        <div className="bg-white p-4 lg:p-5 rounded-2xl shadow-sm border border-gray-100 animate-scaleIn">
          <div className="flex flex-col sm:flex-row gap-3 items-end">
            <div className="w-full sm:w-48">
              <label className="text-xs text-gray-400 block mb-1 font-medium"><i className="fas fa-users mr-1" />Guruh</label>
              <select value={selectedGroup} onChange={e => setSelectedGroup(e.target.value)} className="input-field">
                <option value="">Tanlang</option>
                {groups.map(g => (
                  <option key={g.id} value={g.id}>
                    {g.name}{g.days ? ` (${g.days})` : ""}
                  </option>
                ))}
              </select>
              {group?.days && (
                <div className="flex gap-1 mt-2">
                  {group.days.split(",").filter(Boolean).map((d: string) => (
                    <span key={d} className="px-2 py-0.5 rounded text-xs font-semibold text-white" style={{ background: "var(--theme-primary)" }}>{d}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="w-full sm:w-40">
              <label className="text-xs text-gray-400 block mb-1 font-medium"><i className="fas fa-calendar-day mr-1" />Sana</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} className="input-field" />
            </div>
            <div className="w-full sm:flex-1">
              <label className="text-xs text-gray-400 block mb-1 font-medium"><i className="fas fa-pen mr-1" />Mavzu</label>
              <input value={topic} onChange={e => setTopic(e.target.value)} className="input-field" />
            </div>
            <button onClick={startLesson} className="btn-primary px-5 py-2.5 rounded-xl font-semibold text-sm cursor-pointer w-full sm:w-auto flex items-center gap-2" style={{ marginTop: "22px" }}>
              <i className="fas fa-play" /> Darsni boshlash
            </button>
          </div>
        </div>
      ) : (
        <div>
          <div className="bg-white p-4 lg:p-5 rounded-2xl shadow-sm border border-gray-100 mb-4 animate-slideIn">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-white text-lg font-bold" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
                  <i className="fas fa-hashtag" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">{group?.name} — {lessonNumber}-dars</h2>
                  <p className="text-sm text-gray-400"><i className="fas fa-calendar-day mr-1" />{date} {topic ? `| ${topic}` : ""}</p>
                </div>
              </div>
              <button onClick={saveAttendance} className="btn-primary px-5 py-2 rounded-xl font-semibold text-sm cursor-pointer w-full sm:w-auto flex items-center gap-2 animate-glow">
                <i className="fas fa-check" /> Saqlash
              </button>
            </div>
            {msg && <div className="mt-3 p-3 bg-green-100 text-green-700 rounded-xl font-medium animate-bounceIn text-sm"><i className="fas fa-check-circle mr-1" />{msg}</div>}
          </div>
          {students.length === 0 ? (
            <div className="text-center py-12 text-gray-400"><i className="fas fa-user text-3xl block mb-2" />Bu guruhda o'quvchilar yo'q</div>
          ) : (
            students.map((s, i) => {
              const cfg = statusConfig[attendances[s.id]] || statusConfig.present
              return (
                <div key={s.id} onClick={() => toggleStatus(s.id)}
                  className="flex items-center justify-between p-4 bg-white rounded-2xl border border-gray-100 mb-2 hover:translate-x-1.5 transition-all cursor-pointer animate-slideUp"
                  style={{ animationDelay: `${i * 0.03}s` }}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-white" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
                      {s.name.charAt(0)}
                    </div>
                    <span className="font-medium text-gray-900">{s.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="px-4 py-1.5 rounded-xl font-semibold text-sm border-2 transition-all hover:scale-105 flex items-center gap-1.5"
                      style={{ background: cfg.bg, borderColor: cfg.border, color: cfg.color }}>
                      <i className={`fas ${cfg.icon}`} /> {cfg.label}
                    </div>
                  </div>
                </div>
              )
            })
          )}
          <div className="flex gap-4 mt-4 text-xs text-gray-400 justify-center items-center">
            <span><i className="fas fa-check-circle text-green-500 mr-1" />Keldi</span>
            <span><i className="fas fa-clock text-yellow-500 mr-1" />Kechikdi</span>
            <span><i className="fas fa-times-circle text-red-500 mr-1" />Kelmadi</span>
            <span className="text-gray-300">|</span>
            <span><i className="fas fa-arrow-pointer mr-1" />Bosing → o'zgaradi</span>
          </div>
        </div>
      )}
    </div>
  )
}