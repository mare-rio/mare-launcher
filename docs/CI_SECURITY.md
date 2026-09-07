# CI and contributor trust

The prepared workflow runs tests and builds an **unsigned** APK on GitHub-hosted runners. It has no signing, publishing or deployment job. Publication of this candidate is on hold; the settings below are requirements to check before creating a public repository, not a claim that they have already been applied.

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

## Settings required before publication

1. **Actions secrets:** keep this repository outside every organisation-secret selection, and add no repository or environment secrets. Audit organisation visibility before creation. Secrets shared with all private repositories can reach a newly created private staging repository; “private” is not a CI isolation control.
2. **Runners:** retain the organisation rule that excludes public repositories from self-hosted runner groups. Use GitHub-hosted runners for this project.
3. **Workflow permissions:** read-only. Disable the option allowing Actions to create or approve pull requests. Do not send write tokens or secrets to fork workflows.
4. **Fork approval:** require approval for all outside contributors’ workflow runs. Approval is permission to execute code; inspect changes before approving.
5. **Branch protection/rulesets:** require pull requests, required checks and CODEOWNER review for `main`; dismiss stale reviews and require review of the latest push. Review direct-push and administrator bypass rights deliberately.
6. **Review ownership:** `.github/CODEOWNERS` names the maintainer for all files. This is enforced only after the matching ruleset requires code-owner approval. Review scripts, lockfiles and vendored assets as well as workflow files.
7. **Action policy:** allow required actions only and enforce full-SHA pinning where available. Keep secret scanning and push protection enabled where supported.

Inspect inherited organisation settings again before switching a repository between private and public. Do not copy another Maré application’s deployment pipeline into this project.

## Signing without giving CI the key

Build and inspect the exact source revision in an environment with no signing credentials or production access. Check the resulting APK and record its SHA-256. Move that reviewed APK to a trusted signing environment, then use a previously reviewed copy of `scripts/sign.py`. The helper verifies the approved digest, invokes an explicitly selected local Android SDK signer, and never builds the project. It does not choose executable paths from artifact metadata.

The signing key stays outside the checkout. Pass its password through an environment variable to the signer, never command arguments, and unset it afterwards. Do not build or run contributor code while the password is present. Environment variables are not protection against code already running as the same user; an isolated signing account or offline machine provides a stronger boundary.

Manual signing still depends on the integrity of the signing helper, Android SDK, operating system and reviewed APK. A digest confirms identity, not whether the code is safe. The final APK and installation ZIP need owner review before any manual publication.
