# Pitmark Cloud v0.21.44

## Social Operator repair

- Fixed posting-gap detection so pending/approved drafts no longer falsely count as daily social coverage.
- Added Instagram to the Social Operator's low-risk daily cadence alongside Facebook and X.
- Added per-platform engagement health reporting.
- Meta/Facebook read-permission failures now mark the operator **degraded** instead of reporting a false healthy run.
- Control Center now shows **Needs Attention** with the real integration error while healthy posting automation continues.
- Added regression tests for daily coverage and degraded-channel behavior.
