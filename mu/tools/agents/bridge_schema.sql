CREATE TABLE IF NOT EXISTS jobs (
  job_id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  status TEXT NOT NULL,
  task_text TEXT NOT NULL,
  scope_hint TEXT,
  wave_class TEXT,
  allow_edits INTEGER NOT NULL DEFAULT 0,
  reader_agent TEXT NOT NULL,
  reviewer_agent TEXT NOT NULL,
  acceptance_checks_json TEXT NOT NULL,
  max_rounds INTEGER NOT NULL DEFAULT 2,
  current_round INTEGER NOT NULL DEFAULT 0,
  terminal_decision TEXT
);

CREATE TABLE IF NOT EXISTS turns (
  turn_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  round_no INTEGER NOT NULL,
  agent_role TEXT NOT NULL,
  status TEXT NOT NULL,
  decision TEXT,
  state_sha_start TEXT NOT NULL,
  state_sha_end TEXT,
  prompt_path TEXT NOT NULL,
  raw_output_path TEXT NOT NULL,
  envelope_json TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

CREATE TABLE IF NOT EXISTS validations (
  validation_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL,
  turn_id TEXT,
  command TEXT NOT NULL,
  exit_code INTEGER NOT NULL,
  result_summary TEXT NOT NULL,
  output_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);
