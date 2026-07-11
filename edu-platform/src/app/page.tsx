"use client"
import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/navigation"

function ParticleBg() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current!
    const ctx = canvas.getContext("2d")!
    let w = canvas.width = window.innerWidth
    let h = canvas.height = window.innerHeight
    const particles: any[] = []
    const count = 60

    for (let i = 0; i < count; i++) {
      particles.push({
        x: Math.random() * w, y: Math.random() * h,
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        r: Math.random() * 3 + 1.5,
        a: Math.random() * 0.3 + 0.1,
      })
    }

    let raf: number
    function draw() {
      ctx.clearRect(0, 0, w, h)
      for (let i = 0; i < count; i++) {
        const p = particles[i]
        p.x += p.vx; p.y += p.vy
        if (p.x < 0 || p.x > w) p.vx *= -1
        if (p.y < 0 || p.y > h) p.vy *= -1
        ctx.beginPath()
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(249,115,22,${p.a})`
        ctx.fill()
        // Connect nearby particles
        for (let j = i + 1; j < count; j++) {
          const p2 = particles[j]
          const dx = p.x - p2.x, dy = p.y - p2.y
          const dist = Math.sqrt(dx * dx + dy * dy)
          if (dist < 120) {
            ctx.strokeStyle = `rgba(249,115,22,${0.08 * (1 - dist / 120)})`
            ctx.lineWidth = 0.5
            ctx.beginPath()
            ctx.moveTo(p.x, p.y)
            ctx.lineTo(p2.x, p2.y)
            ctx.stroke()
          }
        }
      }
      raf = requestAnimationFrame(draw)
    }
    draw()

    const resize = () => { w = canvas.width = window.innerWidth; h = canvas.height = window.innerHeight }
    window.addEventListener("resize", resize)
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize) }
  }, [])

  return <canvas ref={canvasRef} className="absolute inset-0 z-0" />
}

export default function LoginPage() {
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const router = useRouter()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(""); setLoading(true)
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, password }),
    })
    if (res.ok) {
      const data = await res.json()
      localStorage.setItem("token", data.token)
      router.push("/dashboard")
    } else {
      const data = await res.json()
      setError(data.error || "Xatolik yuz berdi")
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-black">
      <ParticleBg />
      {/* 3D floating shapes */}
      <div className="absolute inset-0 z-[1] pointer-events-none" style={{ perspective: "1200px" }}>
        <div className="absolute top-[15%] left-[10%] w-20 h-20 border-2 border-orange-500/20 rounded-2xl animate-float"
          style={{ animationDelay: "0s", animationDuration: "6s", transform: "rotateX(45deg) rotateZ(15deg)" }} />
        <div className="absolute top-[60%] right-[12%] w-28 h-28 border-2 border-orange-500/15 rounded-full animate-float"
          style={{ animationDelay: "1.5s", animationDuration: "8s", transform: "rotateY(30deg)" }} />
        <div className="absolute top-[30%] right-[20%] w-16 h-16 border-2 border-purple-500/20 animate-float"
          style={{ animationDelay: "3s", animationDuration: "7s", transform: "rotateX(60deg) rotateZ(45deg)" }} />
        <div className="absolute bottom-[20%] left-[15%] w-24 h-24 border border-orange-500/10 rounded-full animate-float"
          style={{ animationDelay: "2s", animationDuration: "9s" }} />
      </div>

      <form onSubmit={handleSubmit}
        className="bg-white/95 backdrop-blur-xl p-10 rounded-3xl shadow-2xl w-full max-w-md z-10 animate-scaleIn border border-white/30 relative"
        style={{ transformStyle: "preserve-3d", perspective: "1000px" }}>
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center text-white text-2xl mx-auto mb-4 animate-float shadow-lg shadow-orange-500/30"
            style={{ transformStyle: "preserve-3d", transform: "rotateY(0deg) rotateX(5deg)" }}>
            <i className="fas fa-graduation-cap" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Akademiya</h1>
          <p className="text-gray-400 text-sm mt-1">O'quv markazi tizimi</p>
        </div>

        {error && <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm text-center mb-4 animate-bounceIn border border-red-100">
          <i className="fas fa-exclamation-circle mr-1" />{error}</div>}

        <div className="relative mb-4">
          <i className="fas fa-user absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Login" value={login} onChange={e => setLogin(e.target.value)}
            className="input-field pl-10" required />
        </div>
        <div className="relative mb-6">
          <i className="fas fa-lock absolute left-4 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="password" placeholder="Parol" value={password} onChange={e => setPassword(e.target.value)}
            className="input-field pl-10" required />
        </div>
        <button type="submit" disabled={loading}
          className="w-full py-3.5 rounded-xl font-semibold text-white transition-all cursor-pointer flex items-center justify-center gap-2 relative overflow-hidden group btn-primary">
          {loading ? <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <i className="fas fa-arrow-right" />}
          {loading ? "Kirilmoqda..." : "Kirish"}
        </button>
      </form>
    </div>
  )
}