# Publish Preciso

Status: version 0.3.0rc1 is published on PyPI and TestPyPI. The GitHub prerelease
is published. The matching Trusted Publishers are configured. Future maintainers
must retain those account settings. A GitHub release and a PyPI release are
separate publications; always verify the upload result.

## One-time account configuration

1. Sign in to PyPI and TestPyPI. These are separate services and accounts.
2. On each service, add a pending Trusted Publisher for a new project named
   `preciso-graphrag`, or add a publisher to that project if you already own it.
   Project name availability and ownership must be verified on the service.
3. Select GitHub Actions and enter these exact values:

   | Field | PyPI | TestPyPI |
   |---|---|---|
   | GitHub owner | `Preciso-GR` | `Preciso-GR` |
   | Repository | `preciso-graphrag` | `preciso-graphrag` |
   | Workflow filename | `publish.yml` | `publish.yml` |
   | Environment | `pypi` | `testpypi` |

4. In GitHub repository settings, configure environments named `pypi` and
   `testpypi`. Restrict who can publish through these environments. Use required
   reviewers where available. The PyPI publisher and workflow environment must match.

Do not put a PyPI password or API token in the repository. The workflow uses
short-lived GitHub OIDC credentials. Setup instructions:
[PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/).

## Review and test

1. Open a PR for the setup feature branch. Wait for the Python matrix, container,
   and package jobs to pass. Review the compatibility notes and current limitations.
2. Merge the reviewed PR into `main`. Do not tag unreviewed feature code.
3. Run the `Publish Python package` workflow manually from `main`. Manual runs
   publish to TestPyPI only. They run the full CI workflow first.
4. Download the TestPyPI wheel without dependencies:

   ```sh
   python -m pip download --no-deps --only-binary=:all: \
     --index-url https://test.pypi.org/simple/ \
     --dest /tmp/preciso-testpypi preciso-graphrag==0.3.0rc1
   ```

5. Test setup from that wheel with `uvx --from /absolute/path/to/the.whl
   preciso-graphrag setup --project /absolute/test-project`. Use a disposable project
   and a temporary `CODEX_HOME` if testing registration. Keep the wheel until that
   development connection is removed. Dependencies resolve from normal PyPI;
   TestPyPI is only the source for the downloaded Preciso wheel.

The account setup, TestPyPI upload, and downloaded-wheel setup test are release
gates. Do not report them as passed until they have been executed. TestPyPI does
not allow replacing an existing version's files; increment the prerelease version
for changed artifacts after a successful upload.

## Publish the reviewed version

1. Complete [release checks](release-checklist.md). State remaining preview limits
   in the release notes. These checks do not establish broad production readiness.
2. Ensure `pyproject.toml`, the changelog, and public setup instructions agree on
   the release version and publication status. Use an immutable annotated tag
   `v0.3.0rc1` on the reviewed commit in `main`.
3. Publish a GitHub prerelease from that tag. This triggers `publish.yml`.
4. The workflow runs CI, checks tag/version equality and main ancestry, builds
   the wheel from the source distribution, and validates metadata and contents.
   Only the separate publishing job has `id-token: write` permission.
5. Confirm the PyPI job succeeded. A GitHub release alone does not prove upload.
6. Test the public installation in a fresh project:

   ```sh
   uvx --from preciso-graphrag==0.3.0rc1 preciso-graphrag setup --project .
   codex mcp list
   ```

7. Reload Codex. Call `get_server_status` and `get_document_workflow`. Update the
   README publication notice only after the public installation succeeds.

## Package contents

GitHub retains source, tests, essential guides, research evidence, and archived
decisions. The wheel contains runtime Python modules, metadata, and the license.
The source distribution adds the files needed to rebuild that wheel. Neither
distribution includes docs, tests, agent skills, MCP JSON examples, model weights,
private documents, or graph data. `scripts/check_distribution.py` enforces this
boundary in CI. The server exposes a baseline extraction contract through
`get_document_workflow`; repository domain skills remain optional source resources.

Model downloads and Codex registration require explicit setup confirmation.
Installing the package alone does not register it with an agent. Automated
registration currently supports Codex. Other clients require manual configuration.

Official workflow reference:
[PyPA publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
