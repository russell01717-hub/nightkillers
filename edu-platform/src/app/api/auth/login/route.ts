import { getUserByLogin } from "@/lib/db"
import bcrypt from "bcryptjs"

export async function POST(req: Request) {
  try {
    const { login, password } = await req.json()
    const user = await getUserByLogin(login)
    if (!user) {
      return Response.json({ error: "Login yoki parol noto'g'ri" }, { status: 401 })
    }

    const match = bcrypt.compareSync(password, user.password)
    if (!match) {
      return Response.json({ error: "Login yoki parol noto'g'ri" }, { status: 401 })
    }

    const { password: _, ...userData } = user
    const token = Buffer.from(JSON.stringify(userData)).toString("base64")

    return Response.json({ token, user: userData })
  } catch (err: any) {
    return Response.json({ error: err.message || "Server xatosi" }, { status: 500 })
  }
}
