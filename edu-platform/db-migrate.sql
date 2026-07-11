-- Auto-migration columns
ALTER TABLE groups ADD COLUMN IF NOT EXISTS days TEXT DEFAULT '';
ALTER TABLE groups ADD COLUMN IF NOT EXISTS subject TEXT DEFAULT '';
ALTER TABLE groups ADD COLUMN IF NOT EXISTS teacher_id INT DEFAULT 0;
ALTER TABLE students ADD COLUMN IF NOT EXISTS start_date TEXT DEFAULT '';

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  login TEXT UNIQUE NOT NULL,
  password TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS groups (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  price_per_lesson INT DEFAULT 0,
  days TEXT DEFAULT '',
  subject TEXT DEFAULT '',
  teacher_id INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS students (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT DEFAULT '',
  group_id INT REFERENCES groups(id) ON DELETE CASCADE,
  balance INT DEFAULT 0,
  start_date TEXT DEFAULT '',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
  id SERIAL PRIMARY KEY,
  group_id INT REFERENCES groups(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  topic TEXT DEFAULT '',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS attendances (
  id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(id) ON DELETE CASCADE,
  lesson_id INT REFERENCES lessons(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
  id SERIAL PRIMARY KEY,
  student_id INT REFERENCES students(id) ON DELETE CASCADE,
  amount INT NOT NULL,
  type TEXT NOT NULL,
  note TEXT DEFAULT '',
  date TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO users (name, login, password, role)
SELECT 'Admin', 'admin', '$2a$10$joXlAMPf2vJrZ/.ub6VMRu84yuLDihg5GtCCjI.jtQy4YdJchzyRS', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'admin');

INSERT INTO users (name, login, password, role)
SELECT 'Sardor', 'sardor', '$2a$10$joXlAMPf2vJrZ/.ub6VMRu84yuLDihg5GtCCjI.jtQy4YdJchzyRS', 'teacher'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'sardor');

INSERT INTO users (name, login, password, role)
SELECT 'G''ayrat', 'gayrat', '$2a$10$joXlAMPf2vJrZ/.ub6VMRu84yuLDihg5GtCCjI.jtQy4YdJchzyRS', 'teacher'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'gayrat');

INSERT INTO users (name, login, password, role)
SELECT 'Shoxali', 'shoxali', '$2a$10$joXlAMPf2vJrZ/.ub6VMRu84yuLDihg5GtCCjI.jtQy4YdJchzyRS', 'teacher'
WHERE NOT EXISTS (SELECT 1 FROM users WHERE login = 'shoxali');