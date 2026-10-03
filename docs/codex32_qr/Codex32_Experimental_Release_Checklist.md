# Codex32 experimental release checklist

**Experimental / public test seeds and testnet or regtest only. No real backups
or funds. This is an independent fork, not an official SeedSigner release.**
The software itself still supports mainnet; wording must not imply an enforced
network restriction. Do not publish until the final physical UX4 checks pass.

## Freeze and identify the tested image

- Retain the exact image that passed physical testing. Record SHA256, byte count,
  target board, app commit, OS commit, Buildroot commit, build arguments, Docker
  image identity and the exact included version.json. Hash before mounting it.
- Current candidate is app `11270918b794f83be5e9051d391599ff607ff655`, OS
  `d13859392660fe512a753bc14ecd0edc86c35510`, Buildroot
  `bf2a2858aa675a14b60f1f9142c65b32652609c1`, Pi Zero 1.3 target `--pi0`.
  Use the tested candidate commit, not an assumed branch-tip commit.
- Publish only the board image tested. A pi0 build covers the pi0 target; it does
  not establish tests for pi02w, pi2 or pi4. Clearly list tested hardware.
- Choose a unique tag such as `v0.8.7-codex32-ec-test.1`, pinned to the candidate
  commit. This is a suggested tag, not an already created release.
- Documentation-only commits added later do not change this image. Link the
  relevant documentation revision explicitly, or attach the guide as an asset.

## Prepare all draft assets

- Tested `.img` with an unambiguous experimental/board filename.
- `SHA256SUMS` for downloadable image files, with exact filenames and sizes in
  the release notes/build receipt. If compressed, hash the downloaded archive as
  well as documenting the decompressed image hash.
- A public build receipt: immutable input commits, exact version metadata, build
  parameters, public preparation steps and hashes of any non-Git build inputs.
  Sanitize local receipts: do not upload absolute PC paths, private photos, keys,
  credentials or all private review/evidence documents.
- The tester guide, public A/C vectors, expected `fab6868a`, focused UX checklist,
  and a concise validation summary with device/runtime limitations.
- Optional maintainer signature of SHA256SUMS, using an established release key
  whose fingerprint users can verify separately. Do not use upstream SeedSigner's
  key/instructions to imply upstream endorsement. Never fabricate a signature.

## Draft, verify, then publish

Create a draft GitHub release in **FractalEncrypt/FractalEncrypt_seedsigner**.
Select the exact candidate tag/commit and mark **This is a pre-release**. Use a
clear title such as **Codex32 EC Test 1 - EXPERIMENTAL - NO REAL FUNDS**. Keep it
out of the latest stable release slot. Upload all assets while it is a draft.

Check the uploaded downloads against local SHA256SUMS, confirm the correct board
and commit, and inspect the complete release text/assets. Then publish only after
the operator confirms physical testing and authorizes that final publication.
No GitHub Actions image/build job is required for this manual release. The current
workflow is a CI artifact builder and does not itself publish a GitHub Release.

Opening paragraph to use in the release notes:

> EXPERIMENTAL INDEPENDENT FORK. For testing with public seeds and testnet/regtest
> only. Do not enter real backups or mainnet seeds, and do not use this image to
> secure funds. Mainnet is not disabled by this build. This is not an official
> SeedSigner release. Please report results with public test data only.

Summarize the bounded correction modes, numbered review/re-entry, unverified
reconstruction warnings, optional fingerprint checks, tested board, known limits,
exact input commits and checksum verification. Do not claim byte-identical
reproducibility until an independent rebuild matches the published image.

## Immutable releases

Immutability is optional for publication, and recommended for this distributed
firmware. It locks the published assets and associated tag, and GitHub generates
an attestation connecting tag, commit and assets. It does not prove that a binary
was reproducibly built from the source or that its behavior is safe.

Enable **Settings -> General -> Releases -> Enable release immutability** before
publishing the new release. It applies to future releases; existing releases do
not automatically become immutable. Assemble every asset in a draft first:
after publication, assets cannot be added/replaced/deleted and the tag cannot be
moved. Notes/title and prerelease status remain editable. A fixed image should
receive a new tag/release (for example test.2), not replace test.1.

Official references:

- [Preventing changes to releases](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes)
- [Immutable releases and attestations](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases)
- [Drafting and managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
