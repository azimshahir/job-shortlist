# Setup backend — langkah demi langkah

Buat sekali sahaja. Ambil masa lebih kurang 30 minit. Anda perlukan:
akaun GitHub (dah ada), akaun Supabase (percuma), akaun Vercel (percuma).

Simpan 6 nilai ini dalam nota sementara (Notepad) semasa buat langkah di
bawah — jangan simpan dalam repo, jangan hantar dalam chat:

| Nama | Dari mana |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API (yang `anon public`) |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API (yang `service_role`) — **rahsia** |
| `SUPABASE_USER_ID` | Supabase → Authentication → Users (UUID akaun anda) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer settings → Fine-grained tokens |
| `GITHUB_REPO` | nama repo, contoh `azimshahir/job-shortlist` |

---

## A. Supabase (pangkalan data)

1. Pergi ke https://supabase.com, **Sign in** dengan GitHub.
2. Tekan **New project**. Nama: `job-shortlist`. Region: **Singapore**.
   Tetapkan Database Password (simpan dalam pengurus kata laluan; jarang
   diperlukan). Tekan **Create new project** dan tunggu 1–2 minit.
3. Di menu kiri tekan **SQL Editor** → **New query**.
4. Buka fail `supabase/migrations/0001_init.sql` dalam repo, salin
   **semua** kandungannya, tampal ke dalam kotak SQL, tekan **Run**.
   Mesej hijau "Success. No rows returned" bermaksud siap.
5. Di menu kiri tekan **Table Editor**. Anda patut nampak 5 jadual:
   `runs`, `jobs`, `job_scores`, `job_actions`, `validation_labels`.
   Tekan **Storage** — patut ada bucket `resumes` (Private).
6. Cipta akaun log masuk anda (satu sahaja):
   **Authentication** → **Users** → **Add user** → **Create new user**.
   Isi email dan kata laluan anda. Tandakan **Auto Confirm User**. Tekan
   **Create user**.
7. Dalam senarai Users, tekan pada baris pengguna itu. Salin **UUID**
   (bentuk `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Ini `SUPABASE_USER_ID`.
8. **Project Settings** (ikon gear di bawah) → **API**. Salin:
   - **Project URL** → `SUPABASE_URL`
   - **anon public** → `SUPABASE_ANON_KEY`
   - **service_role** (tekan **Reveal**) → `SUPABASE_SERVICE_ROLE_KEY`.
     Ini kunci penuh; jangan letak di mana-mana selain GitHub Secrets.

## B. GitHub (scraper berjalan di sini)

9. Buka repo di GitHub → **Settings** → **Secrets and variables** →
   **Actions** → **New repository secret**. Tambah 3 secret, satu-satu:
   - Name `SUPABASE_URL`, Secret = nilai dari langkah 8
   - Name `SUPABASE_SERVICE_ROLE_KEY`, Secret = nilai dari langkah 8
   - Name `SUPABASE_USER_ID`, Secret = nilai dari langkah 7
10. (Pilihan, hanya jika mahu bayar API) Tambah juga `LLM_PROVIDER`
    (`anthropic` atau `openai`) dan `ANTHROPIC_API_KEY` atau
    `OPENAI_API_KEY`. **Tak wajib** — lihat bahagian E.
11. Uji: tab **Actions** → **Daily job shortlist** → **Run workflow** →
    **Run workflow**. Tunggu 10–15 minit. Bila hijau, buka Supabase →
    **Table Editor** → `runs`: ada satu baris dengan `status = ok`.

## C. Token untuk butang "Scrape sekarang"

12. GitHub → klik gambar profil → **Settings** → paling bawah
    **Developer settings** → **Personal access tokens** →
    **Fine-grained tokens** → **Generate new token**.
13. Token name: `job-shortlist-vercel`. Expiration: **1 year**.
    Repository access: **Only select repositories** → pilih repo ini.
    Permissions → **Repository permissions** → cari **Actions** → pilih
    **Read and write**. (Itu sahaja; tak perlu yang lain.)
14. Tekan **Generate token**. Salin token (bermula `github_pat_`). Ini
    `GITHUB_TOKEN`. Ia hanya ditunjuk sekali.

## D. Vercel (web app)

15. Pergi ke https://vercel.com, **Sign in** dengan GitHub → **Add New…**
    → **Project** → **Import** repo ini.
16. Di skrin konfigurasi: **Root Directory** → tekan **Edit** → pilih `web`.
    Framework akan dikesan sebagai Next.js.
17. Buka **Environment Variables** dan tambah:
    - `NEXT_PUBLIC_SUPABASE_URL` = `SUPABASE_URL`
    - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = `SUPABASE_ANON_KEY` (yang anon,
      **bukan** service_role)
    - `GITHUB_TOKEN` = token dari langkah 14
    - `GITHUB_REPO` = `pemilik/nama-repo` (contoh `azimshahir/job-shortlist`)
    - `RESUME_MODE` = `queue` (lalai; tukar ke `api` hanya jika buat langkah 10)
18. Tekan **Deploy**. Bila siap, buka URL yang diberi dan log masuk dengan
    email + kata laluan dari langkah 6.

## E. Tailored Resume — tanpa bayar API

Butang **Tailored Resume** di dashboard tidak memanggil AI berbayar. Ia cuma
menanda job itu sebagai `requested`. Untuk jana fail `.docx`:

19. Buka Claude Code dalam folder repo dan taip `/resume`.
20. Claude akan baca senarai job yang diminta, tulis kandungan resume
    sendiri (guna langganan Claude anda, bukan API key), jalankan
    `python scraper/render_resume.py` yang membina `.docx`, muat naik ke
    Supabase Storage dan tanda `ready`.
21. Refresh dashboard → butang bertukar **Download .docx**.

Supaya `/resume` boleh sambung ke Supabase dari komputer anda, set 3
pembolehubah persekitaran ini sekali (Windows: **Settings → System → About →
Advanced system settings → Environment Variables → New**):
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_USER_ID`.

Peraturan yang tidak boleh dilangkau (dua-dua laluan):
- `scraper/candidate_profile.yaml` mesti diisi dulu — selagi ada `TODO_`,
  permintaan ditolak dengan sebab **"CV induk belum diisi"**.
- Senarai `must_not_claim` dan `framing_rules` dalam fail itu disemak
  secara automatik sebelum `.docx` dibina.

Laluan pilihan (bayar API): jika langkah 10 dibuat dan `RESUME_MODE=api` di
Vercel, butang itu akan terus lancarkan workflow **Tailored resume (API
path)** di GitHub, yang jalankan `scraper/make_resume.py`. Hasilnya sama.

## F. Pindah sejarah lama (sekali sahaja, pilihan)

Jika `scraper/job_history.db` lama ada rekod (job yang pernah dishortlist /
applied), pindahkan supaya sistem tidak cadangkan semula job yang sama:

22. Pastikan 3 pembolehubah dari bahagian E dah diset.
23. Dalam terminal: `cd scraper` kemudian
    `python migrate_sqlite.py --dry-run` — ia tunjuk berapa baris akan
    dipindah, tanpa menulis apa-apa.
24. Jika nampak betul: `python migrate_sqlite.py`. Selamat diulang; ia
    tidak akan padam atau kurangkan apa-apa.

## G. Semak semuanya jalan

- Supabase → `runs` bertambah satu baris setiap pagi ~07:40.
- Dashboard → tekan **Scrape sekarang** → dalam 1 minit baris `runs` baru
  muncul dengan `status = running`, kemudian `ok`.
- Tanda satu job **Applied** → esok ia tidak lagi dalam Disyorkan.

Jika ada yang gagal, mesej ralat dalam GitHub → **Actions** → run yang
merah biasanya menyebut nama secret yang hilang. Betulkan di langkah 9.
