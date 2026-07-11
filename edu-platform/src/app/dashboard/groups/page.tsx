"use client"
import { useEffect, useState } from "react"

const DAYS_UZ = ["Yak", "Du", "Se", "Chor", "Pay", "Jum", "Shan"]
const DAYS_FULL = ["Yakshanba", "Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba"]
const SUBJECTS = [
  { value: "", label: "Tanlanmagan" },
  { value: "arabic", label: "Arab tili", color: "from-orange-400 to-orange-600" },
  { value: "english", label: "Ingliz tili", color: "from-blue-400 to-blue-600" },
]

export default function GroupsPage() {
  const [groups, setGroups] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [desc, setDesc] = useState("")
  const [price, setPrice] = useState("")
  const [days, setDays] = useState<string[]>([])
  const [subject, setSubject] = useState("")
  const [teacherId, setTeacherId] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    try { setUser(JSON.parse(atob(localStorage.getItem("token") || ""))) } catch {}
  }, [])

  function toggleDay(d: string) {
    setDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d].sort())
  }

  function load() {
    fetch("/api/groups").then(r => r.json()).then(setGroups)
    fetch("/api/users").then(r => r.json()).then(setUsers)
  }
  useEffect(load, [])

  function openCreate() {
    setEditId(null); setName(""); setDesc(""); setPrice(""); setDays([]); setSubject(""); setTeacherId(""); setShowForm(true); setError("")
  }

  function openEdit(g: any) {
    setEditId(g.id); setName(g.name); setDesc(g.description || ""); setPrice(g.pricePerLesson?.toString() || "")
    setDays(g.days ? g.days.split(",").filter(Boolean) : []); setSubject(g.subject || ""); setTeacherId(g.teacherId?.toString() || ""); setShowForm(true); setError("")
  }

  async function save(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError("")
    try {
      const body = { name, description: desc, pricePerLesson: parseInt(price) || 0, days: days.join(","), subject, teacherId: parseInt(teacherId) || 0 }
      if (editId) {
        const res = await fetch("/api/groups", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: editId, ...body }) })
        if (!res.ok) { const d = await res.json(); setError(d.error || "Xatolik"); setSaving(false); return }
      } else {
        const res = await fetch("/api/groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        if (!res.ok) { const d = await res.json(); setError(d.error || "Xatolik"); setSaving(false); return }
      }
      setName(""); setDesc(""); setPrice(""); setDays([]); setSubject(""); setTeacherId(""); setEditId(null); setShowForm(false); load()
    } catch (e: any) { setError(e.message) }
    setSaving(false)
  }

  async function del(id: number) {
    if (!confirm("O'chirasizmi?")) return
    await fetch(`/api/groups?id=${id}`, { method: "DELETE" }); load()
  }

  const teachers = users.filter(u => u.role === "teacher")

  return (
    <div className="animate-fadeIn">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Guruhlar</h1>
          <p className="text-sm text-gray-400"><i className="fas fa-users mr-1" style={{ color: "var(--theme-primary)" }} />{user?.role === "admin" ? "Barcha guruhlar" : "Sizning guruhlaringiz"}</p>
        </div>
        <button onClick={openCreate} className="btn-primary flex items-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm cursor-pointer w-full sm:w-auto justify-center">
          <i className="fas fa-plus" /> Yangi guruh
        </button>
      </div>
      {showForm && (
        <form onSubmit={save} className="bg-white p-4 lg:p-5 rounded-2xl shadow-sm border border-gray-100 mb-6 animate-slideIn">
          {error && <div className="mb-3 p-3 bg-red-50 text-red-600 rounded-xl text-sm"><i className="fas fa-exclamation-circle mr-1" />{error}</div>}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1 font-medium">Nomi</label>
              <input value={name} onChange={e => setName(e.target.value)} className="input-field" required />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1 font-medium">Izoh</label>
              <input value={desc} onChange={e => setDesc(e.target.value)} className="input-field" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1 font-medium">Dars narxi (so'm)</label>
              <input type="number" value={price} onChange={e => setPrice(e.target.value)} className="input-field" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1 font-medium">Fan</label>
              <select value={subject} onChange={e => setSubject(e.target.value)} className="input-field">
                {SUBJECTS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1 font-medium">O'qituvchi</label>
              <select value={teacherId} onChange={e => setTeacherId(e.target.value)} className="input-field">
                <option value="">Tanlanmagan</option>
                {teachers.map(t => <option key={t.id} value={t.id}>{t.name} ({t.login})</option>)}
              </select>
            </div>
          </div>
          <div className="mb-4">
            <label className="text-xs text-gray-400 block mb-2 font-medium">Hafta kunlari</label>
            <div className="flex flex-wrap gap-2">
              {DAYS_UZ.map(d => (
                <button key={d} type="button" onClick={() => toggleDay(d)}
                  className={`px-4 py-2 rounded-xl text-sm font-semibold transition-all cursor-pointer ${days.includes(d) ? "text-white shadow-lg scale-105" : "bg-gray-100 text-gray-500 hover:bg-gray-200"}`}
                  style={days.includes(d) ? { background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` } : {}}>
                  {d}
                </button>
              ))}
            </div>
            {days.length > 0 && <p className="text-xs mt-1" style={{ color: "var(--theme-primary)" }}>{days.map(d => DAYS_FULL[DAYS_UZ.indexOf(d)]).join(", ")}</p>}
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="btn-primary px-5 py-2.5 rounded-xl font-semibold text-sm cursor-pointer flex items-center gap-2">
              {saving ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <i className="fas fa-check" />}
              {saving ? "Saqlanmoqda..." : "Saqlash"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className="px-5 py-2.5 rounded-xl font-semibold text-sm bg-gray-100 text-gray-500 hover:bg-gray-200 cursor-pointer">
              <i className="fas fa-times mr-1" /> Bekor qilish
            </button>
          </div>
        </form>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {groups.map(g => {
          const teacher = users.find(u => u.id === g.teacherId)
          const subj = SUBJECTS.find(s => s.value === g.subject)
          return (
            <div key={g.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 card-hover animate-scaleIn relative overflow-hidden group"
              style={{ transformStyle: "preserve-3d" }}>
              <div className="absolute top-0 right-0 w-32 h-32 rounded-full -mr-10 -mt-10 group-hover:scale-150 transition-transform duration-500"
                style={{ background: subject === "english" ? "rgba(59,130,246,0.05)" : "var(--theme-primary)", opacity: 0.05 }} />
              <div className="relative">
                <div className="flex justify-between items-start mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                      style={{ background: g.subject === "english" ? "linear-gradient(135deg, #3b82f6, #2563eb)" : `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
                      <i className={`fas ${g.subject === "arabic" ? "fa-language" : g.subject === "english" ? "fa-book-open" : "fa-users"} text-white`} />
                    </div>
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{g.name}</h3>
                      {g.description && <p className="text-xs text-gray-400 mt-0.5">{g.description}</p>}
                      {g.subject && <span className="text-[10px] font-semibold" style={{ color: g.subject === "english" ? "#3b82f6" : "var(--theme-primary)" }}>
                        {subj?.label}
                      </span>}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => openEdit(g)} className="p-1.5 rounded-lg text-xs hover:bg-orange-50 transition cursor-pointer" style={{ color: "var(--theme-primary)" }}>
                      <i className="fas fa-pen-to-square" />
                    </button>
                    <button onClick={() => del(g.id)} className="p-1.5 rounded-lg text-xs hover:bg-red-50 text-red-500 transition cursor-pointer">
                      <i className="fas fa-trash-can" />
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-4 text-sm">
                  <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl" style={{ background: "color-mix(in srgb, var(--theme-primary) 10%, transparent)" }}>
                    <i className="fas fa-coins" style={{ color: "var(--theme-primary)" }} />
                    <span className="font-bold" style={{ color: "var(--theme-primary)" }}>{g.pricePerLesson?.toLocaleString()}</span>
                    <span className="text-gray-400 text-xs">so'm/dars</span>
                  </div>
                  <div className="bg-blue-50 px-3 py-1.5 rounded-xl">
                    <i className="fas fa-user-graduate text-blue-500 mr-1" />
                    <span className="text-blue-600 font-bold">{g.studentCount}</span>
                    <span className="text-gray-400 text-xs ml-1">o'quvchi</span>
                  </div>
                  {teacher && (
                    <div className="bg-purple-50 px-3 py-1.5 rounded-xl">
                      <i className="fas fa-chalkboard-user text-purple-500 mr-1" />
                      <span className="text-purple-600 font-bold text-xs">{teacher.name}</span>
                    </div>
                  )}
                </div>
                {g.days && (
                  <div className="mt-3 flex gap-1.5 items-center">
                    <i className="fas fa-calendar-week text-xs text-gray-400" />
                    {g.days.split(",").filter(Boolean).map((d: string) => (
                      <span key={d} className="px-2.5 py-1 rounded-lg text-xs font-semibold text-white" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>{d}</span>
                    ))}
                    <span className="text-xs text-gray-400 ml-auto">har hafta</span>
                  </div>
                )}
              </div>
            </div>
          )
        })}
        {groups.length === 0 && (
          <div className="col-span-full py-16 text-center text-gray-400">
            <i className="fas fa-book-open text-5xl block mb-3" />
            <p className="text-lg font-medium">Guruhlar mavjud emas</p>
          </div>
        )}
      </div>
    </div>
  )
}