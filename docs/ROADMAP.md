# ROADMAP — Job Shortlist Dashboard

Satu fail untuk tahu kita di mana. Kemas kini setiap kali fasa siap.
Rujukan: `docs/PRD.md` (apa), `CLAUDE.md` (peraturan).

**Kos keseluruhan: RM0.** Supabase free, Vercel free, GitHub Actions free,
resume guna langganan Claude sedia ada. Tiada API key.

---

## Status ringkas

| Fasa | Apa | Siapa | Status |
|---|---|---|---|
| 0 | Pindah Python ke `scraper/` | Orchestrator | ✅ Siap 12 Sep |
| 1 | Backend: Supabase schema, sink, workflows, API routes | Agent Backend | 🔄 Berjalan |
| 2 | Designer: spec 4 skrin + mock | Agent Designer | ✅ Siap 12 Sep |
| 3 | Frontend: Next.js — login, Hari Ini, Semua Job, Runs, Detail | Agent Frontend | ⏳ Lepas Fasa 1 |
| 4 | Butang Scrape sekarang + Minta resume | Backend + Frontend | ⏳ Lepas Fasa 3 |
| 5 | `/resume` command (jana .docx guna langganan Claude) | Backend | ⏳ Lepas Fasa 1 |
| 6 | Setup akaun (Supabase, Vercel, secrets) | **Azim** + Orchestrator | ⏳ Lepas Fasa 1 |
| 7 | Deploy Vercel + smoke test | Orchestrator | ⏳ Lepas 3, 4, 6 |
| 8 | Validasi seminggu, tune rules | Azim + Orchestrator | ⏳ Lepas 7 |

---

## Fasa 0 — Monorepo ✅

- [x] `scraper/` mengandungi semua Python
- [x] 81 ujian lulus dari lokasi baru
- [x] Workflow, `.gitignore`, `/jobs` ikut path baru
- [x] `docs/PRD.md` v1.1, `CLAUDE.md`

## Fasa 1 — Backend 🔄

- [ ] `supabase/migrations/0001_init.sql` — 5 table + RLS + bucket `resumes`
- [ ] `scraper/sink.py` — tulis runs / jobs / job_scores
- [ ] `scraper/history.py` — `SupabaseHistoryStore`
- [ ] `scraper/pipeline.py --sink supabase`
- [ ] `scraper/resume_queue.py` + `render_resume.py`
- [ ] `scraper/test_sink.py` — ujian tanpa network
- [ ] `.github/workflows/daily.yml` tulis ke Supabase
- [ ] `web/lib/supabase/{server,client,types}.ts`
- [ ] `web/lib/github.ts` + `web/app/api/{scrape,resume}/route.ts`
- [ ] `.claude/commands/resume.md`
- [ ] `docs/backend.md` — panduan setup untuk Azim (Bahasa Melayu)
- [ ] `scraper/migrate_sqlite.py` — pindah history lama sekali

## Fasa 2 — Designer ✅

- [x] `docs/design.md` — spec: table, badge, keadaan butang resume, mobile, empty/error
- [x] `docs/design-components.md` — senarai komponen shadcn + custom
- [x] `docs/mock-hari-ini.html` — mock visual skrin utama
- [ ] Nota untuk Frontend: butang resume ikut aliran queue (Minta → Dalam senarai → Download); prasyarat hanya CV, bukan API key

## Fasa 3 — Frontend ⏳

- [ ] Login (Supabase Auth, email + password)
- [ ] App shell: nav Hari Ini / Semua Job / Runs, logout
- [ ] **Hari Ini** — satu table: # · Job · Company · Lokasi · Source · Family · KW · Sem · Final · Sebab · Status · Link · Resume
- [ ] Baris Disyorkan di atas (highlight), baki ranked di bawah dengan sebab
- [ ] Dropdown Status (new/applied/interview/offer/rejected/ignored) — simpan ke `job_actions`
- [ ] Dropdown Label (strong/acceptable/weak/reject) — simpan ke `validation_labels`
- [ ] Butang Link (apply terus vs lihat posting)
- [ ] Butang Resume — 3 keadaan: kelabu+sebab / Minta / Download
- [ ] Baris funnel + banner amaran "0 scraped"
- [ ] **Semua Job** — table + filter (status, family, source, tarikh) + search
- [ ] **Job Detail** drawer — description, semua skor, sebab, sejarah, nota
- [ ] **Runs** — senarai run + funnel
- [ ] Responsive: table scroll mendatar di telefon
- [ ] `npm run build` + `lint` lulus

## Fasa 4 — Butang aksi ⏳

- [ ] **Scrape sekarang** → `/api/scrape` → GitHub dispatch → poll `runs` → toast siap
- [ ] **Minta resume** → `/api/resume` → `resume_status = requested`
- [ ] Poll `resume_status` → butang bertukar ke Download bila `ready`

## Fasa 5 — `/resume` di Claude Code ⏳

- [ ] Baca senarai `requested` dari Supabase
- [ ] Tolak dengan sebab jelas jika `candidate_profile.yaml` masih ada `TODO_`
- [ ] Tulis kandungan (langganan Claude, bukan API) ikut guardrail: tiada reka, metrik kekal, Copilot Facilitator wajib
- [ ] Jana `.docx` (Calibri, hitam, 2 muka, ATS) → simpan local + muat naik Storage
- [ ] Tanda `ready`, tunjuk senarai dalam chat

## Fasa 6 — Setup akaun (Azim buat, ikut `docs/backend.md`) ⏳

- [ ] Buat projek Supabase (percuma) → salin URL + 2 key
- [ ] Jalankan migration SQL (copy-paste satu fail)
- [ ] Buat satu user login (email + password) → salin user id
- [ ] GitHub Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_USER_ID`
- [ ] Buat GitHub token (fine-grained, actions: write, repo ini sahaja)
- [ ] Buat projek Vercel, sambung repo, root directory = `web/`
- [ ] Vercel env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO`
- [ ] Jalankan `migrate_sqlite.py` sekali untuk bawa history lama

## Fasa 7 — Deploy + smoke test ⏳

- [ ] Vercel deploy hijau
- [ ] Login dari telefon
- [ ] Tekan Scrape sekarang → run baru muncul dalam ~10 minit
- [ ] Tanda satu job Applied → hilang dari Disyorkan selepas scrape seterusnya
- [ ] Tekan Minta resume → `/resume` di Claude Code → Download berfungsi
- [ ] Matikan routine cloud Claude lama (tak perlu lagi)

## Fasa 8 — Validasi ⏳

- [ ] Guna seminggu; label 30 job (strong/acceptable/weak/reject)
- [ ] `calibrate.py --report` dari label sebenar
- [ ] Semak `career_family_reason` untuk salah tapis
- [ ] Keputusan threshold 60 berdasarkan label, bukan agak-agak

---

## Terhalang — perlu Azim

| Perkara | Kesan | Bila |
|---|---|---|
| **CV induk** (employer, tarikh, bullet, pendidikan) | `/resume` tak boleh jalan; `candidate_profile.yaml` ada 10 `TODO_` | Sebelum Fasa 5 diuji |
| Akaun Supabase + Vercel | Fasa 6 | Lepas Fasa 1 siap |
| Push ke GitHub | Actions + Vercel baca dari repo | Setiap kali saya minta |

## Sengaja tidak dibuat

- API key LLM — dibuang, guna langganan
- Email — dibuang
- Cloud routine Claude scrape — tak boleh (403 LinkedIn); routine sedia ada akan dimatikan di Fasa 7
- LinkedIn recruiter posts, Playwright — v2
- Edit threshold/weights dari UI — v2

## Log

- **11 Sep** — Scraper siap, 952 job, semantic + career gating + history. Email dibuang. Cloud routine gagal (403).
- **12 Sep** — Pivot ke dashboard. PRD v1.1, CLAUDE.md, Fasa 0 siap. Backend + Designer dilancarkan.
