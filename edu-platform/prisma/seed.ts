import { PrismaClient } from "@prisma/client"
import bcrypt from "bcryptjs"

const prisma = new PrismaClient()

async function main() {
  const existing = await prisma.user.findUnique({ where: { login: "admin" } })
  if (!existing) {
    await prisma.user.create({
      data: {
        name: "Admin",
        login: "admin",
        password: bcrypt.hashSync("admin123", 10),
        role: "admin",
      },
    })
    console.log("Admin user created (admin / admin123)")
  } else {
    console.log("Admin user already exists")
  }
}

main().catch(console.error).finally(() => prisma.$disconnect())
