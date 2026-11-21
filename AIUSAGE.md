<!-- SPDX-License-Identifier: MIT -->
<!-- AI-assisted documentation; maintainer review required. -->

# AI Usage

This fork has used AI-assisted tools to help draft and review changes to its
HailoRT build integration, Docker build scripts, GitHub Actions workflows,
validation scripts, and documentation.

## Responsibilities

- Human maintainers decide which changes to accept, commit, and release.
- AI-generated suggestions are not evidence that code works. Changes must pass
  source review, security checks, architecture-specific builds, and tests.
- AI-generated code or documentation must be reviewed for errors, licensing,
  security, and compatibility with upstream Frigate before publication.
- Do not submit credentials, private camera addresses, API tokens, or private
  deployment configurations to public AI prompts or commit them to this fork.
- AI tools must not independently approve releases or publish Docker images.

## Verification and limitations

The software-only CI jobs validate image dependencies and application imports
on `linux/amd64` and `linux/arm64`. No Hailo accelerator is attached to those
runners. Tests of the PCIe driver, Multi-Process Service, actual inference,
and live camera integration require a physical Hailo-equipped host.

A successful CI build is not a claim that Hailo hardware inference has been
verified on both architectures. The test environment and evidence should be
recorded in the release notes.

## Attribution

Upstream Frigate and third-party components retain their own licenses,
authorship, and notices. AI assistance does not change those requirements.
