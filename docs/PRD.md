# PRD — Job Shortlist Dashboard

**Versi:** 1.1 (MVP) · **Tarikh:** 12 Sep 2026 · **Status:** untuk kelulusan

## 1. Masalah

Pipeline scraping dah berfungsi (JobSpy → rules → embeddings → gating → history),
tapi cara *guna* dia berselerak: email, GitHub Actions, Claude Code, cloud routine.
Pengguna bukan developer dan cuma nak satu tempat: log masuk, tengok table, tanda
apa yang dah apply. Tiada.

## 2. Matlamat

Satu web app peribadi di mana pengguna boleh:

1. Log masuk (satu akaun)
2. Tengok shortlist hari ini dalam table, dengan sebab setiap job dipilih atau ditolak
3. Tekan satu butang untuk scrape sekarang, tanpa buka GitHub
4. Track status setiap job (Baru → Applied → Interview → Offer / Rejected / Ignored)
5. Label job (strong / acceptable / weak / reject) supaya sistem boleh dikalibrasi
6. Tengok sejarah run dan funnel setiap hari

7. Tekan **Tailored Resume** pada mana-mana job dan dapat `.docx` yang disesuaikan

**Bukan matlamat MVP:** LinkedIn recruiter posts, Playwright, multi-user, mobile app.

**Prasyarat untuk Tailored Resume** (butang wujud dari hari pertama, tapi kelabu
sehingga kedua-dua ini dipenuhi — sebab ditunjuk bila hover):
- `candidate_profile.yaml` diisi dari CV induk (sekarang ada 10 `TODO_`). Sistem
  **tidak akan** reka pengalaman; ini garis merah yang sedia ada.
- Satu API key LLM (`ANTHROPIC_API_KEY` atau `OPENAI_API_KEY`) di GitHub Secrets.

## 3. Pengguna

Seorang: Azim. Finance ops, 5 tahun, KL/Selangor. Bukan developer. Guna dari
laptop dan telefon (responsive, bukan native).

## 4. Seni bina

```
┌──────────────────────┐   workflow_dispatch   ┌──────────────────────────┐
│  Next.js (Vercel)    │ ───────────────────►  │  GitHub Actions           │
│  - Supabase Auth     │                        │  scraper/pipeline.py      │
│  - Dashboard tables  │                        │  (JobSpy + embeddings)    │
│  - Status / labels   │                        └────────────┬─────────────┘
└──────────┬───────────┘                                     │ writes
           │ reads / writes (RLS)                            ▼
           │                          ┌──────────────────────────────────┐
           └────────────────────────► │  Supabase (Postgres + Auth)       │
                                      │  runs · jobs · job_scores ·       │
                                      │  job_actions · validation_labels  │
                                      └──────────────────────────────────┘
```

**Kenapa scrape masih di GitHub Actions:** Vercel serverless ada had 10–60s dan
tiada torch; cloud Claude sekat LinkedIn (403, terbukti 11 Sep). Actions terbukti
scrape 927 job. Ia infrastruktur tersembunyi — pengguna tak nampak, cuma tekan butang.

**Kenapa Supabase:** Postgres + Auth + RLS + REST dalam satu, free tier cukup,
dan `history.py` sedia ada storage abstraction — tambah satu backend sahaja.

## 5. Struktur repo (monorepo, repo sedia ada)

```
job-shortlist/
├── scraper/          ← kod Python sedia ada dipindah ke sini (tiada perubahan logik)
│   ├── pipeline.py, filters.py, semantic.py, careers.py, ranking.py, ...
│   ├── history.py    ← tambah SupabaseHistoryStore
│   └── sink.py       ← BARU: tulis runs/jobs/job_scores ke Supabase
├── web/              ← BARU: Next.js app (Vercel root directory = web/)
├── supabase/
│   └── migrations/   ← schema SQL
├── .github/workflows/daily.yml   ← scrape + tulis ke Supabase
├── docs/PRD.md
└── CLAUDE.md
```

## 6. Model data (Supabase)

| Table | Tujuan | Kunci |
|---|---|---|
| `runs` | Satu baris setiap scrape: masa, funnel counts, status, trigger (cron/manual) | `id` |
| `jobs` | Satu baris setiap job unik (fingerprint dari `history.py`): title, company, location, source, urls, description, first/last seen | `job_id` |
| `job_scores` | Skor job **dalam satu run**: keyword, semantic_raw, final, rank, career family, selection status + reason | `(run_id, job_id)` |
| `job_actions` | Status tracking pengguna: `new · shortlisted · applied · interview · offer · rejected · ignored`, tarikh, nota, `resume_status` (none · pending · ready · failed), `resume_url` | `job_id` |
| `validation_labels` | `strong · acceptable · weak · reject` — input kepada `calibrate.py` | `job_id` |

Semua table ada `user_id` + RLS `auth.uid() = user_id`. Scraper tulis guna
service-role key (rahsia di GitHub Secrets), web baca guna anon key + sesi user.

## 7. Skrin

### 7.1 Login
Email + password (Supabase Auth). Tiada sign-up terbuka — akaun dicipta sekali di Supabase dashboard.

### 7.2 Hari Ini (landing) — skrin utama

Satu table, format sama seperti report chat yang sedia ada:

| # | Job | Company | Lokasi | Source | Family | KW | Sem | Final | Sebab | Status | **Link** | **Tailored Resume** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

- Baris **Disyorkan** di atas (highlight), baris **Ranked tak disyorkan** di bawah
  dengan *Sebab* = out of scope / intern / bawah 60 / cooldown. Satu table, dua
  kumpulan — bukan dua table berasingan.
- **Link** — butang buka posting (job_url_direct jika ada, jika tidak job_url),
  tab baru. Ikon berbeza untuk "apply terus" vs "lihat posting".
- **Tailored Resume** — butang dengan tiga keadaan:
  - *kelabu + sebab* bila prasyarat belum dipenuhi (§2)
  - *Generate* → picu penjanaan (§8), tunjuk spinner, ~1–2 minit
  - *Download .docx* bila siap; klik semula = jana semula
- **Status** — dropdown: new · applied · interview · offer · rejected · ignored
- **Label** — dropdown kecil: strong · acceptable · weak · reject (untuk kalibrasi)
- Baris funnel di atas table; butang **Scrape sekarang** di kanan atas
- Job dengan status ≠ new diwarnakan (applied = hijau, ignored = kelabu pudar)

### 7.3 Semua Job
Table penuh semua job pernah dilihat. Filter: status, career family, source, tarikh.
Sort mana-mana lajur. Search title/company. Ini tempat track pipeline permohonan.

### 7.4 Job Detail (drawer / modal)
Description penuh, semua skor, `career_family_reason`, `selection_reason`,
`matched_keywords`, sejarah (first seen, berapa kali muncul, run mana). Tukar status,
label, nota.

### 7.5 Runs
Senarai setiap run: masa, trigger, funnel counts, berapa disyorkan, status (ok / gagal / 0 scraped). Klik → shortlist run itu.

### 7.6 Settings
Baca sahaja untuk MVP: threshold semasa, weights, cooldown. (Edit = v2.)

## 8. Aliran utama

**Pagi:** Actions cron 7:40 → scrape → tulis Supabase → pengguna buka app → Hari Ini.

**Scrape sekarang:** butang → `POST /api/scrape` (Vercel route) → GitHub
`workflow_dispatch` API dengan PAT dari env → app poll table `runs` untuk status.

**Tanda applied:** dropdown → `job_actions` upsert → scraper baca table ini melalui
`SupabaseHistoryStore` → job tak muncul lagi dalam disyorkan. *Logik cooldown dan
applied yang sedia ada kekal; hanya storan bertukar.*

**Label:** dropdown → `validation_labels` → `calibrate.py` boleh tarik terus.

**Tailored Resume:** butang → `POST /api/resume` (Vercel route) → GitHub
`workflow_dispatch` pada `resume.yml` dengan input `job_id` → Actions jalankan
`scraper/llm.py` + `scraper/resume.py` yang **sedia ada** (dengan semua guardrail:
must_not_claim, framing_rules, metrik tak diubah, Copilot Facilitator wajib) →
muat naik `.docx` ke Supabase Storage bucket `resumes` → kemas kini
`job_actions.resume_url` + `resume_status` → app poll dan tukar butang ke Download.

*Kenapa Actions, bukan Vercel:* panggilan LLM + docx ambil 30–90s; Vercel hobby
had 10s. Actions tiada had itu, dan kod Python resume dah wujud dan diuji.

## 9. Keperluan bukan fungsi

- Load Hari Ini < 2s (data kecil, satu query per table)
- Responsive: table boleh scroll mendatar pada telefon
- Tiada LLM API dipanggil oleh web app
- Rahsia: hanya di Vercel env + GitHub Secrets; tiada dalam kod
- Ujian Python sedia ada (81) kekal lulus selepas pindah folder

## 10. Peringkat

| Fasa | Hasil | Dilakukan oleh |
|---|---|---|
| 0 | Pindah Python ke `scraper/`, ujian lulus | Orchestrator |
| 1 | Schema Supabase + RLS + `sink.py` + `SupabaseHistoryStore` + Actions tulis ke DB | Backend |
| 2 | Design system + wireframe 4 skrin | Designer |
| 3 | Next.js: auth, Hari Ini, Semua Job, Detail, Runs | Frontend |
| 4 | Butang Scrape sekarang (GitHub dispatch route) | Backend + Frontend |
| 5 | Tailored Resume: `resume.yml`, Storage bucket, `/api/resume`, butang 3-keadaan | Backend + Frontend |
| 6 | Deploy Vercel, smoke test end-to-end | Orchestrator |

Fasa 1 dan 2 selari. Fasa 3 bermula selepas 1 (perlu schema) dan boleh ambil design
secara berperingkat.

## 11. Keputusan yang dibuat (yolo)

| Keputusan | Pilihan | Sebab |
|---|---|---|
| Frontend | Next.js 15 App Router, TypeScript, Tailwind, shadcn/ui | Vercel-native, table components siap |
| Backend | Supabase (Postgres, Auth, RLS) | Satu servis, free tier, Python client wujud |
| Scrape runtime | GitHub Actions | Satu-satunya yang terbukti capai LinkedIn |
| Auth | Email + password, satu user | Cukup; OAuth = v2 |
| Table | TanStack Table | Sort/filter/search tanpa backend |
| State | Server Components + Supabase client; tiada Redux | Data kecil |
| Deploy | Vercel (web), Supabase cloud (db) | VPS = pilihan kemudian, tiada halangan |

## 12. Risiko

| Risiko | Mitigasi |
|---|---|
| LinkedIn mula sekat GitHub runner | Actions self-hosted di VPS — kod sama, runner tukar |
| Supabase free tier pause selepas 7 hari tak aktif | Cron harian mengelakkannya |
| `job_history.db` lama tak sepadan | Fasa 1 migrate sekali dari SQLite ke Supabase |
| Skop melarat (LLM, resume) | Bukan matlamat MVP, dinyatakan di §2 |

## 13. Definisi siap

Pengguna log masuk dari telefon, nampak shortlist pagi ini dalam satu table, tekan
Link untuk buka posting, tekan Scrape sekarang dan nampak run baru siap, tanda satu
job Applied dan ia hilang dari Disyorkan selepas refresh. Butang Tailored Resume
wujud pada setiap baris — kelabu dengan sebab jelas sehingga CV induk dan API key
disediakan, dan menjana `.docx` boleh muat turun sebaik sahaja kedua-duanya ada.
Semua tanpa buka GitHub, Gmail, atau Claude Code.
