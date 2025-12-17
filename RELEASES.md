# Release Management

This integration uses version-based releases with support for multiple release channels in HACS.

## Release Channels

HACS supports the following release channels:

- **Stable** (default): Latest stable release - recommended for production use
- **Beta**: Pre-release versions with new features - may contain bugs
- **Test**: Development versions - for testing only, may be unstable
- **Custom Version**: Install a specific version by tag (e.g., `v1.0.0`)

## Creating a Release

### 1. Update Version Numbers

Before creating a release, update the version in:

- `custom_components/ship24/manifest.json` - Update the `version` field
- `hacs.json` - Update the `version` field (if present)

Example:
```json
{
  "version": "1.0.1"
}
```

### 2. Update CHANGELOG.md

Add an entry for the new version in `CHANGELOG.md` following the format:

```markdown
## [1.0.1] - 2025-01-XX

### Fixed
- Fixed issue with webhook processing

### Changed
- Improved error handling
```

### 3. Commit Changes

```bash
git add .
git commit -m "Bump version to 1.0.1"
git push
```

### 4. Create Git Tag

Create a tag for the release. Use semantic versioning:

**For Stable Releases:**
```bash
git tag -a v1.0.1 -m "Release version 1.0.1"
git push origin v1.0.1
```

**For Beta Releases:**
```bash
git tag -a v1.0.1-beta -m "Beta release version 1.0.1"
git push origin v1.0.1-beta
```

**For Test Releases:**
```bash
git tag -a v1.0.1-test -m "Test release version 1.0.1"
git push origin v1.0.1-test
```

### 5. Create GitHub Release

1. Go to GitHub repository → Releases → "Draft a new release"
2. Select the tag you just created (e.g., `v1.0.1`)
3. Set the release title: `Release 1.0.1` (or `Beta 1.0.1`, `Test 1.0.1`)
4. Copy the changelog entry for this version into the release notes
5. For beta/test releases, check "Set as a pre-release"
6. Click "Publish release"

## Branch Strategy

For multiple release channels, you can use branches:

- **main/master**: Stable releases
- **beta**: Beta releases
- **test**: Test/development releases

Users can select the branch in HACS when installing or updating.

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Incompatible API changes
- **MINOR** (0.1.0): New functionality, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

## HACS Integration

HACS will automatically:
- Detect releases from GitHub releases
- Allow users to choose between stable, beta, and test channels
- Show version information
- Display the logo (if `logo.png` exists in repository root)

## Logo

Place a `logo.png` file (128x128px, PNG format) in the repository root for HACS to display it.

