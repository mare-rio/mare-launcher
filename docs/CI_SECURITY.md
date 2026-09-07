# CI and contributor trust

The workflow runs tests and builds an **unsigned** APK on GitHub-hosted runners. It has no signing, publishing or deployment job. Installable APKs and installer ZIPs are signed and published locally after release validation; contributor workflows never receive the signing key.

## What malicious code can access

A workflow runs programs from the repository, including tests, build scripts and dependencies. Treat a contributor’s changes to any of these as executable code. If a job has a signing key, cloud credential or write token, malicious code in that job can read and send it elsewhere. Masking secrets in logs does not prevent exfiltration.

Ordinary fork pull-request workflows do not receive Actions secrets; their `GITHUB_TOKEN` is normally read-only. This is one boundary, not a guarantee about merged code, collaborator branches, manual runs or privileged workflows. In particular, checking out a contributor’s revision under `pull_request_target`, or executing their artifacts from a privileged `workflow_run` job, can cross that boundary. See [GitHub’s secure-use guidance](https://docs.github.com/en/actions/reference/security/secure-use) and [secret availability](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).

## Repository workflow

- Triggers: `pull_request`, push to `main`, and manual checks.
- Explicit `permissions: contents: read`; unspecified token permissions are absent.
- Only GitHub-hosted runners; no organisation runner or internal network connection.
- Actions pinned to full commit SHAs; checkout does not persist Git credentials.
- Public locked npm dependencies, with lifecycle scripts disabled during dependency installation.
- No secret expressions, environment credentials, OIDC token, privileged PR trigger, cache or artifact-consumption chain.
- No automatic signing, release creation, package publication or deployment.

The policy test catches accidental drift in this workflow. A malicious contributor can change tests too; required human review and repository settings remain essential. SHA pinning prevents an action tag from moving but does not make the pinned code inherently trustworthy.

## Repository protection policy

1. **Actions secrets:** keep this repository outside every organisation-secret selection, and add no repository or environment secrets. Audit organisation visibility before creation. Secrets shared with all private repositories can reach a newly created private staging repository; “private” is not a CI isolation control.
2. **Runners:** retain the organisation rule that excludes public repositories from self-hosted runner groups. Use GitHub-hosted runners for this project.
3. **Workflow permissions:** read-only. Disable the option allowing Actions to create or approve pull requests. Do not send write tokens or secrets to fork workflows.
4. **Fork approval:** require approval for all outside contributors’ workflow runs. Approval is permission to execute code; inspect changes before approving.
5. **Branch protection/rulesets:** `main` requires a PR and native code-owner review, with zero blanket approvals and no bypass actors. A PR authored by a code owner satisfies ownership; other PRs need approval from the owning team. Stale approvals are dismissed when code changes, and review conversations must be resolved. Requiring a separate latest-push approval would also block a sole member’s own PR, so it is disabled for this authorship-or-review policy. A separate ruleset requires Linux, Windows, macOS and Android CI and protects branch history, also with no bypass actors. The initial branch-creation exception does not apply to changes to the existing `main`.
6. **Review ownership:** `.github/CODEOWNERS` assigns every file, including itself and all workflows, to `@mare-rio/launcher-maintainers`. GitHub Teams only admit organisation members; the team has explicit repository write access and contains the organisation’s current member. Add new launcher maintainers to this team. Outside collaborators and installed apps are not code owners and cannot satisfy the ownership rule. GitHub evaluates the base branch’s CODEOWNERS, so an unapproved PR cannot remove its own approval requirement. [GitHub code-owner rules](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).
7. **Action policy:** enforce full-SHA pinning. The organisation's selected-action policy is inherited; GitHub does not permit a narrower repository allowlist under the current parent policy. This workflow uses only the four reviewed GitHub-owned action versions pinned in `.github/workflows/ci.yml`. Keep secret scanning and push protection enabled where supported.
8. **Security reporting:** keep private vulnerability reporting enabled. The launcher's own enforced security configuration enables it together with secret scanning, push protection and Dependabot alerts and security updates.

Inspect inherited organisation settings again before switching a repository between private and public. Do not copy another Maré application’s deployment pipeline into this project.

## Signing without giving CI the key

Build and inspect the exact source revision in an environment with no signing credentials or production access. Check the resulting APK and record its SHA-256. Move that reviewed APK to a trusted signing environment, then use a previously reviewed copy of `scripts/sign.py`. The helper verifies the approved digest, invokes an explicitly selected local Android SDK signer, and never builds the project. It does not choose executable paths from artifact metadata.

The signing key stays outside the checkout. Pass its password through an environment variable to the signer, never command arguments, and unset it afterwards. Do not build or run contributor code while the password is present. Environment variables are not protection against code already running as the same user; an isolated signing account or offline machine provides a stronger boundary.

Manual signing still depends on the integrity of the signing helper, Android SDK, operating system and reviewed APK. A digest confirms identity, not whether the code is safe. The final APK and installation ZIP need owner review before any manual publication.
