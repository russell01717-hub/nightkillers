"use client"
import Link from "next/link"
import { useRouter, usePathname } from "next/navigation"
import { useEffect, useState } from "react"

const THEMES = [
  { name: "Orange", primary: "#f97316", secondary: "#ea580c" },
  { name: "Blue", primary: "#3b82f6", secondary: "#2563eb" },
  { name: "Green", primary: "#22c55e", secondary: "#16a34a" },
  { name: "Purple", primary: "#a855f7", secondary: "#9333ea" },
  { name: "Rose", primary: "#f43f5e", secondary: "#e11d48" },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<any>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const [newPass, setNewPass] = useState("")
  const [passMsg, setPassMsg] = useState("")
  const [showTheme, setShowTheme] = useState(false)
  const [theme, setTheme] = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("theme") || "Orange"
    return "Orange"
  })

  useEffect(() => {
    const t = THEMES.find(t => t.name === theme)
    if (t) {
      document.documentElement.style.setProperty("--theme-primary", t.primary)
      document.documentElement.style.setProperty("--theme-secondary", t.secondary)
    }
  }, [theme])

  useEffect(() => {
    const token = localStorage.getItem("token")
    if (!token) { router.push("/"); return }
    try {
      const u = JSON.parse(atob(token))
      setUser(u)
      if (u.role === "teacher") {
        // Teacher can't access admin pages
        const adminPaths = ["/dashboard/users", "/dashboard/payments"]
        if (adminPaths.includes(pathname)) router.push("/dashboard")
      }
    } catch { router.push("/") }
  }, [])

  function changeTheme(name: string) {
    setTheme(name); localStorage.setItem("theme", name); setShowTheme(false)
  }

  async function changePassword() {
    if (!newPass || !user) return
    const res = await fetch("/api/users", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: user.id, name: user.name, password: newPass }),
    })
    if (res.ok) { setPassMsg("Parol o'zgartirildi"); setNewPass("") }
    else { setPassMsg("Xatolik") }
    setTimeout(() => setPassMsg(""), 3000)
  }

  function logout() { localStorage.removeItem("token"); router.push("/") }

  const isAdmin = user?.role === "admin"
  const isTeacher = user?.role === "teacher"

  const allLinks = [
    { href: "/dashboard", label: "Dashboard", icon: "fa-chart-simple", show: true },
    { href: "/dashboard/groups", label: "Guruhlar", icon: "fa-users", show: true },
    { href: "/dashboard/students", label: "O'quvchilar", icon: "fa-user-graduate", show: true },
    { href: "/dashboard/attendance", label: "Davomat", icon: "fa-check-circle", show: true },
    { href: "/dashboard/lessons", label: "Darslar", icon: "fa-book", show: true },
    { href: "/dashboard/payments", label: "To'lovlar", icon: "fa-credit-card", show: isAdmin },
    { href: "/dashboard/users", label: "Foydalanuvchilar", icon: "fa-user-shield", show: isAdmin },
  ]
  const links = allLinks.filter(l => l.show)

  return (
    <div className="flex h-screen bg-gray-50">
      {sidebarOpen && <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={() => setSidebarOpen(false)} />}

      <aside className={`fixed lg:static inset-y-0 left-0 z-50 w-64 flex flex-col p-6 text-white transition-transform duration-300 ${sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}`}
        style={{ background: "linear-gradient(180deg, #0f0f0f 0%, #1a1a2e 100%)" }}>
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
            <i className="fas fa-graduation-cap text-white text-lg" />
          </div>
          <div>
            <h2 className="text-lg font-bold">Akademiya</h2>
            <p className="text-xs" style={{ color: "var(--theme-primary)" }}>
              {isAdmin ? "Admin panel" : user?.name || ""} {user?.login === "sardor" || user?.login === "shoxali" ? "• Arab tili" : user?.login === "gayrat" ? "• Ingliz tili" : ""}
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          {links.map(l => {
            const active = pathname === l.href
            return (
              <Link key={l.href} href={l.href} onClick={() => setSidebarOpen(false)}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm transition-all ${active ? "font-semibold" : "text-gray-400 hover:bg-white/5 hover:text-white hover:translate-x-1"}`}
                style={active ? { background: `${THEMES.find(t => t.name === theme)?.primary}33`, color: THEMES.find(t => t.name === theme)?.primary } : {}}>
                <i className={`fas ${l.icon} w-5 text-center`} /> {l.label}
                {!l.show && isTeacher && <i className="fas fa-lock text-2xs ml-auto opacity-50" />}
              </Link>
            )
          })}
        </nav>

        {/* Theme picker */}
        <div className="relative mb-2">
          <button onClick={() => setShowTheme(!showTheme)}
            className="flex items-center gap-2 w-full px-4 py-2 rounded-xl text-xs text-gray-400 hover:bg-white/5 transition cursor-pointer">
            <i className="fas fa-palette" /> Rang
            <span className="ml-auto w-4 h-4 rounded-full" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }} />
          </button>
          {showTheme && (
            <div className="absolute bottom-full left-0 right-0 mb-1 bg-gray-800 rounded-xl p-2 animate-slideIn shadow-xl border border-gray-700 z-50">
              <div className="flex gap-1.5 justify-center">
                {THEMES.map(t => (
                  <button key={t.name} onClick={() => changeTheme(t.name)}
                    className={`w-8 h-8 rounded-full transition-all cursor-pointer ${theme === t.name ? "ring-2 ring-white scale-110" : "hover:scale-110"}`}
                    style={{ background: `linear-gradient(135deg, ${t.primary}, ${t.secondary})` }}
                    title={t.name} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Profile */}
        <div className="mb-3 p-3 rounded-xl bg-white/5">
          <p className="text-sm text-gray-300 font-medium"><i className="fas fa-user-circle mr-1.5" />{user?.name || "Admin"}</p>
          <p className="text-xs text-gray-500 mb-2">{user?.login || ""} {isTeacher && "(o'qituvchi)"}</p>
          <button onClick={() => setShowProfile(!showProfile)} className="text-xs transition cursor-pointer" style={{ color: "var(--theme-primary)" }}>
            <i className="fas fa-key mr-1" /> Parolni o'zgartirish
          </button>
          {showProfile && (
            <div className="mt-2 animate-slideIn">
              <input type="password" value={newPass} onChange={e => setNewPass(e.target.value)} placeholder="Yangi parol"
                className="w-full px-3 py-1.5 rounded-lg text-sm bg-white/10 border border-white/20 text-white placeholder-gray-500 focus:outline-none mb-2" />
              <button onClick={changePassword} className="w-full py-1.5 rounded-lg text-xs font-semibold text-white cursor-pointer flex items-center justify-center gap-1"
                style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
                <i className="fas fa-check" /> Saqlash
              </button>
              {passMsg && <p className="text-xs text-green-400 mt-1"><i className="fas fa-check-circle mr-1" />{passMsg}</p>}
            </div>
          )}
        </div>

        <button onClick={logout} className="flex items-center gap-3 px-4 py-2.5 text-gray-400 hover:bg-red-500/10 hover:text-red-400 rounded-xl text-sm transition-all cursor-pointer">
          <i className="fas fa-sign-out-alt w-5 text-center" /> Chiqish
        </button>
      </aside>

      <main className="flex-1 overflow-y-auto w-full">
        <div className="lg:hidden flex items-center justify-between p-4 bg-white border-b border-gray-100 sticky top-0 z-30">
          <button onClick={() => setSidebarOpen(true)} className="text-xl cursor-pointer"><i className="fas fa-bars text-gray-700" /></button>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs"
              style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
              <i className="fas fa-graduation-cap" />
            </div>
            <span className="font-semibold text-sm">Akademiya</span>
          </div>
          <div className="w-8" />
        </div>
        <div className="p-4 lg:p-8">{children}</div>
      </main>
    </div>
  )
}