import * as jsonDb from "./db-json"

function loadImpl(): typeof jsonDb {
  if (process.env.DATABASE_URL) {
    try {
      return require("./db-sql")
    } catch { /* fallback to JSON */ }
  }
  return jsonDb
}

const impl = loadImpl()

export const getUsers = impl.getUsers
export const getUserByLogin = impl.getUserByLogin
export const getUserById = impl.getUserById
export const createUser = impl.createUser
export const updateUser = impl.updateUser
export const deleteUser = impl.deleteUser
export const getGroups = impl.getGroups
export const getGroup = impl.getGroup
export const createGroup = impl.createGroup
export const updateGroup = impl.updateGroup
export const deleteGroup = impl.deleteGroup
export const getStudents = impl.getStudents
export const createStudent = impl.createStudent
export const deleteStudent = impl.deleteStudent
export const getStudent = impl.getStudent
export const getLessons = impl.getLessons
export const createLesson = impl.createLesson
export const findLessonByGroupAndDate = impl.findLessonByGroupAndDate
export const getTodayAttendance = impl.getTodayAttendance
export const getMonthAttendances = impl.getMonthAttendances
export const getStudentMonthAttendances = impl.getStudentMonthAttendances
export const setAttendance = impl.setAttendance
export const getPayments = impl.getPayments
export const createPayment = impl.createPayment
export const getStats = impl.getStats
