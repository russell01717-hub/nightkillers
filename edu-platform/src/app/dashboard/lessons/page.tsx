"use client"
import { useEffect, useState } from "react"

export default function LessonsPage() {
  const [lessons, setLessons] = useState<any[]>([])
  const [user, setUser] = useState<any>(null)

  useEffect(() => {
    try { setUser(JSON.parse(atob(localStorage.getItem("token") || ""))) } catch {}
  }, [])

  const teacherParams = user?.role === "teacher" ? `?role=teacher&teacherId=${user.id}` : ""
  useEffect(() => { fetch(`/api/lessons${teacherParams}`).then(r => r.json()).then(setLessons) }, [teacherParams])

  const lessonMap: Record<string, number> = {}
  const lessonsWithNum = lessons.map(l => {
    const key = `${l.groupId}_${l.date?.substring(0, 7)}`
    if (!lessonMap[key]) lessonMap[key] = 0
    lessonMap[key]++
    return { ...l, lessonNum: lessonMap[key] }
  })

  return (
    <div className="animate-fadeIn">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Darslar tarixi</h1>
        <p className="text-sm text-gray-400"><i className="fas fa-book mr-1" style={{ color: "var(--theme-primary)" }} />Barcha o'tilgan darslar</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {lessonsWithNum.map(l => (
          <div key={l.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 card-hover animate-scaleIn">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-white text-sm font-bold" style={{ background: `linear-gradient(135deg, var(--theme-primary), var(--theme-secondary))` }}>
                <i className="fas fa-hashtag" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{l.groupName}</h3>
                <p className="text-xs text-gray-400"><i className="fas fa-calendar-day mr-1" />{l.date}</p>
              </div>
            </div>
            {l.topic && <p className="text-xs text-gray-500 mb-3 italic"><i className="fas fa-quote-left mr-1" />{l.topic}</p>}
            <div className="flex gap-2 text-xs">
              <span className="px-2.5 py-1 rounded-lg bg-green-100 text-green-700 font-semibold">
                <i className="fas fa-check-circle mr-1" />{l.presentCount}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-yellow-100 text-yellow-700 font-semibold">
                <i className="fas fa-clock mr-1" />{l.totalCount - l.presentCount - l.absentCount}
              </span>
              <span className="px-2.5 py-1 rounded-lg bg-red-100 text-red-700 font-semibold">
                <i className="fas fa-times-circle mr-1" />{l.absentCount}
              </span>
            </div>
          </div>
        ))}
        {lessonsWithNum.length === 0 && (
          <div className="col-span-full py-16 text-center text-gray-400">
            <i className="fas fa-book-open text-5xl block mb-3" />
            <p className="text-lg font-medium">Darslar mavjud emas</p>
          </div>
        )}
      </div>
    </div>
  )
}