Process the tailored-resume queue. Reply in Malay, short.

The dashboard's "Tailored Resume" button sets `job_actions.resume_status='requested'`
in Supabase. This command turns each request into a `.docx` WITHOUT any paid
LLM API call: YOU write the tailored content (you are the subscription), the
Python code renders, uploads and marks it ready.

Prerequisites (env, never in the repo): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`SUPABASE_USER_ID`. If any is missing, `python scraper/resume_queue.py` fails
loudly — tell the user which one and stop.

Steps:

1. `cd scraper && python resume_queue.py --json` — lists the queue and prints
   every requested job as JSON (title, company, location, full description,
   `job_id`). If it prints "Queue empty", say so and stop.

2. Load `scraper/candidate_profile.yaml`. If `python -c "import candidate; print(candidate.has_placeholders(candidate.load_profile()))"`
   prints a non-empty list, do NOT write anything. For every requested job run
   `python -c "import resume_queue; resume_queue.mark_failed('<job_id>', 'CV induk belum diisi')"`
   and tell the user: CV induk belum diisi — isi `TODO_` dalam
   `scraper/candidate_profile.yaml` dulu. Stop.

3. For each requested job, write ONE JSON object in exactly the shape of
   `llm.RESPONSE_SCHEMA` (see `scraper/llm.py`): keys `overall_suitability`,
   `suitability_rationale`, `strongest_matching_experience`, `gaps`, `risks`,
   `interview_positioning`, `worth_applying`, `worth_applying_reason`,
   `tailored_summary`, `tailored_bullets` (list of `{employer, title, dates,
   bullets}`), `tailored_skills`. Follow `SYSTEM_PROMPT` in `llm.py` and the
   profile's `must_not_claim` + `framing_rules` to the letter:
   - never invent experience, employers, dates, metrics or system proficiency;
   - keep every metric in a kept bullet verbatim; drop a whole bullet rather
     than weaken it;
   - NAV work is "contributing inputs to daily NAV production", never owning
     the calculation;
   - the Agrobank ERM title is Executive;
   - Microsoft Copilot Training Facilitator stays in.
   Save it to a temp file, e.g. `%TEMP%/resume_<n>.json` (Windows) or
   `/tmp/resume_<n>.json`.

4. `cd scraper && python render_resume.py "<job_id>" "<path to json>"`.
   It re-checks the placeholders, scans your JSON for `must_not_claim`
   phrases, builds the `.docx` with `resume.build_resume`, uploads it to the
   private `resumes` bucket and sets `resume_status='ready'`. If it prints
   `REFUSED:` or `FAILED:`, the job is already marked `failed` with the reason
   in `job_actions.notes` — fix the JSON and rerun, or tell the user why.

5. Reply in Malay: one line per job — title, company, `READY` or the reason
   it failed. Remind the user to refresh the dashboard; the button now shows
   Download .docx.

Never call a paid LLM. Never edit `candidate_profile.yaml`. Never change
ranking rules here.
