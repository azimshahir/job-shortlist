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
| 1 | Backend: Supabase schema, sink, workflows, API routes | Agent Backend | ✅ Siap 12 Sep |
| 2 | Designer: spec 4 skrin + mock | Agent Designer | ✅ Siap 12 Sep |
| 3 | Frontend: Next.js — login, Hari Ini, Semua Job, Runs, Detail | Agent Frontend | ✅ Siap 13 Sep |
| 4 | Butang Scrape sekarang + Minta resume | Backend + Frontend | ✅ Siap (belum diuji live) |
| 5 | `/resume` command (jana .docx guna langganan Claude) | Backend | ✅ Siap (belum diuji — perlu CV) |
| 6 | Setup akaun (Supabase, Vercel, secrets) | **Azim** + Orchestrator | 🟡 **Giliran Azim** — `docs/backend.md` |
| 7 | Deploy Vercel + smoke test | Orchestrator | ⏳ Lepas Fasa 6 |
| 8 | Validasi seminggu, tune rules | Azim + Orchestrator | ⏳ Lepas 7 |

---

## Fasa 0 — Monorepo ✅

- [x] `scraper/` mengandungi semua Python
- [x] 81 ujian lulus dari lokasi baru
- [x] Workflow, `.gitignore`, `/jobs` ikut path baru
- [x] `docs/PRD.md` v1.1, `CLAUDE.md`

## Fasa 1 — Backend ✅

- [x] `supabase/migrations/0001_init.sql` — 5 table + RLS + bucket `resumes`
- [x] `scraper/sink.py` — tulis runs / jobs / job_scores
- [x] `scraper/history.py` — `SupabaseHistoryStore`
- [x] `scraper/pipeline.py --sink supabase`
- [x] `scraper/resume_queue.py` + `render_resume.py`
- [x] `scraper/test_sink.py` — ujian tanpa network
- [x] `.github/workflows/daily.yml` tulis ke Supabase
- [x] `web/lib/supabase/{server,client,types}.ts`
- [x] `web/lib/github.ts` + `web/app/api/{scrape,resume}/route.ts`
- [x] `.claude/commands/resume.md`
- [x] `docs/backend.md` — panduan setup untuk Azim (Bahasa Melayu)
- [x] `scraper/migrate_sqlite.py` — pindah history lama sekali

## Fasa 2 — Designer ✅

- [x] `docs/design.md` — spec: table, badge, keadaan butang resume, mobile, empty/error
- [x] `docs/design-components.md` — senarai komponen shadcn + custom
- [x] `docs/mock-hari-ini.html` — mock visual skrin utama
- [ ] Nota untuk Frontend: butang resume ikut aliran queue (Minta → Dalam senarai → Download); prasyarat hanya CV, bukan API key

## Fasa 3 — Frontend ✅

- [x] Login (Supabase Auth, email + password)
- [x] App shell: nav Hari Ini / Semua Job / Runs, logout
- [x] **Hari Ini** — satu table: # · Job · Company · Lokasi · Source · Family · KW · Sem · Final · Sebab · Status · Link · Resume
- [x] Baris Disyorkan di atas (highlight), baki ranked di bawah dengan sebab
- [x] Dropdown Status (new/applied/interview/offer/rejected/ignored) — simpan ke `job_actions`
- [x] Dropdown Label (strong/acceptable/weak/reject) — simpan ke `validation_labels`
- [x] Butang Link (apply terus vs lihat posting)
- [x] Butang Resume — 3 keadaan: kelabu+sebab / Minta / Download
- [x] Baris funnel + banner amaran "0 scraped"
- [x] **Semua Job** — table + filter (status, family, source, tarikh) + search
- [x] **Job Detail** drawer — description, semua skor, sebab, sejarah, nota
- [x] **Runs** — senarai run + funnel
- [x] Responsive: table scroll mendatar di telefon
- [x] `npm run build` + `lint` lulus

## Fasa 4 — Butang aksi ✅

- [x] **Scrape sekarang** → `/api/scrape` → GitHub dispatch → poll `runs` → toast siap
- [x] **Minta resume** → `/api/resume` → `resume_status = requested`
- [x] Poll `resume_status` → butang bertukar ke Download bila `ready`

## Fasa 5 — `/resume` di Claude Code ⏳

- [ ] Baca senarai `requested` dari Supabase
- [ ] Tolak dengan sebab jelas jika `candidate_profile.yaml` masih ada `TODO_`
- [ ] Tulis kandungan (langganan Claude, bukan API) ikut guardrail: tiada reka, metrik kekal, Copilot Facilitator wajib
- [ ] Jana `.docx` (Calibri, hitam, 2 muka, ATS) → simpan local + muat naik Storage
- [ ] Tanda `ready`, tunjuk senarai dalam chat

## Fasa 6 — Setup akaun (Azim buat, ikut `docs/backend.md`) ⏳

- [ ] Buat projek Supabase (percuma) → salin URL + 2 key
- [ ] Jalankan migration SQL: `0001_init.sql` kemudian `0002_views.sql`
- [ ] Buat satu user login (email + password) → salin user id
- [ ] GitHub Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_USER_ID`
- [ ] Buat GitHub token (fine-grained, actions: write, repo ini sahaja)
- [ ] Buat projek Vercel, sambung repo, root directory = `web/`
- [ ] Vercel env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `GITHUB_TOKEN`, `GITHUB_REPO` (+ `NEXT_PUBLIC_RESUME_PREREQ_OK=true` selepas CV diisi)
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
- **13 Sep** — Backend + Designer siap (112 ujian). Frontend siap, build hijau. Semua kod siap; tinggal Fasa 6 (akaun) dan 7 (deploy).
