/**
 * Fire a GitHub Actions workflow_dispatch. Server-only: needs GITHUB_TOKEN
 * (fine-grained PAT, "Actions: read and write" on this repo) and
 * GITHUB_REPO ("owner/name"), both set in Vercel env. Never import this from
 * a client component.
 */

export type WorkflowFile = "daily.yml" | "resume.yml";

export class GitHubDispatchError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "GitHubDispatchError";
    this.status = status;
  }
}

function env(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new GitHubDispatchError(
      `Missing env ${name} (set it in Vercel project settings)`,
      500,
    );
  }
  return value;
}

/**
 * POST /repos/{owner}/{repo}/actions/workflows/{file}/dispatches
 * Resolves on HTTP 204. `ref` defaults to GITHUB_REF env or "main".
 */
export async function dispatchWorkflow(
  file: WorkflowFile,
  inputs: Record<string, string> = {},
  ref: string = process.env.GITHUB_REF ?? "main",
): Promise<void> {
  const token = env("GITHUB_TOKEN");
  const repo = env("GITHUB_REPO");
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    throw new GitHubDispatchError(
      `GITHUB_REPO must look like owner/name, got "${repo}"`,
      500,
    );
  }

  const url = `https://api.github.com/repos/${repo}/actions/workflows/${file}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref, inputs }),
    cache: "no-store",
  });

  if (res.status === 204) return;

  let detail = "";
  try {
    const body = (await res.json()) as { message?: string };
    detail = body.message ? `: ${body.message}` : "";
  } catch {
    // no JSON body
  }
  throw new GitHubDispatchError(
    `GitHub dispatch of ${file} failed (HTTP ${res.status})${detail}`,
    res.status,
  );
}
