# Windows Release Checklist (Step 23)

The Windows CI workflow builds and smoke-tests the frozen executable, then uploads
both the standalone EXE and a versioned ZIP containing the EXE and SHA256SUMS.txt.

## Automated release gates

- [x] Python syntax compilation and pytest suite configured in CI
- [x] PyInstaller executable build configured in CI
- [x] Frozen application startup smoke check configured in CI
- [x] Versioned ZIP packaging and SHA-256 checksum configured in CI
- [ ] Latest packaging workflow completed successfully (check GitHub Actions)
- [ ] SHA-256 checksum independently verified against the extracted executable

## Manual Windows acceptance (required before public release)

- [ ] Download the ZIP from the successful GitHub Actions run
- [ ] Extract the ZIP on a clean Windows x64 PC
- [ ] Verify the checksum in PowerShell:
  `(Get-FileHash .\\SMT_Dimension_Analyzer.exe -Algorithm SHA256).Hash.ToLowerInvariant()`
  Compare with the first value in `SHA256SUMS.txt`
- [ ] Double-click the EXE and verify the GUI appears
- [ ] Import representative CAD, BOM, and Gerber files
- [ ] Check component matching, dimension review and manual acceptance/rejection
- [ ] Export Excel and TXT and verify the dimensions and provenance
- [ ] Confirm the app closes cleanly and no antivirus/security warnings require investigation
- [ ] Record known limitations and approve the version before publishing

## Versioning

Push builds use `ci-<short commit SHA>` in the package filename.
For a public release, use a reviewed version tag and publish the verified ZIP.
A successful CI run is **not** equivalent to hands-on Windows acceptance.
