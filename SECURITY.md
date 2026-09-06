# Security policy

rushstats processes local, potentially untrusted CSV files. It never evaluates cell
contents or sends data to a remote service. Reports can contain category values,
column names and group labels from the input: review reports before sharing them.
Input-byte and group-count limits do not impose a hard process-memory limit.

## Reporting a vulnerability

Use GitHub's **Security → Report a vulnerability** option on this repository when
available. Maintainers must enable private vulnerability reporting in repository
settings. If that option is unavailable, open an issue requesting a private contact
channel, without exploit details, credentials or private data. Do not attach real
sensitive CSVs to public issues.

Include the affected version, platform, reproduction using synthetic input, expected
and observed behavior, and potential impact. Please allow time for investigation
before public disclosure; no response-time guarantee is made.

## Supported versions

Security fixes target the latest release on the 0.x line. Older releases do not have
a backport guarantee. The API is still evolving; review the changelog when upgrading.
