# Pitmark Cloud v0.21.40 — PRT setup and growth metrics

PRT download buttons were never calling the existing download analytics endpoint. The Support Hub also offered little guidance on Early Access activation, and the seven-day activity metric ignored sessions that started before its cutoff.

- Connect the homepage and Support Hub download links to anonymous click tracking. Requests use keepalive, and failure never cancels or waits before a download.
- Count website download clicks separately from completed downloads and unique installs. Automatic updater traffic is not counted by the website listener.
- Count unique seven-day active devices using last session activity; show that metric in PRT Analytics.
- Add direct application/download links, activation and Windows setup steps, and a prefilled bug-report email template to the Support Hub.
- Search all FAQ answers even while collapsed or previously filtered out. Show a helpful empty state and expose topic selection to assistive technology.

Validation: nine dependency-free JavaScript regression tests cover download failure/navigation behavior and FAQ search/filter recovery. Changed Python modules compile successfully. The full Python application was not run locally because its dependencies could not be installed in this environment.

The Windows app remains v0.16.79. Installer bytes, updater compatibility routes, and release manifest are unchanged. Historical missing download clicks cannot be reconstructed.
