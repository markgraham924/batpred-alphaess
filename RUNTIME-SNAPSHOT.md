# Deployed AlphaESS runtime snapshot, 21 September 2026

This branch preserves the deployed `v9.0.2-alphaess.4` source with the native
E.ON Optimise modules from upstream PR 5148 and the existing local planning
fixes. It is a deployment snapshot, not an upgrade to the complete upstream PR.

All 95 deployed Python files were compared with this checkout. They matched
after newline normalisation before code formatting; the formatter subsequently
collapsed one existing condition in `plan.py` without changing its syntax tree.
`runtime-source-manifest.json` records the SHA-256 of each normalised source
file for restoration checks. No household configuration, account credentials,
tokens, debug dumps or private backups are included.

The snapshot preserves the published-price execution boundary, six-day
forecast continuation, local timezone display and non-positive export-price
handling. Native import/export sensors provide planner prices. The existing
HA Optimise forecast integration is still required for the continuation feed.
Do not remove that integration until its forecast input is replaced.

Rebuilds require an add-on image containing `pycognito==2024.5.1`, packaged in
[the add-on change](https://github.com/markgraham924/predbat_addon/pull/1).
`requirements.txt` also declares this dependency for standalone installations.
The rest of the dependency graph is not hash-locked.

Restore source and private add-on configuration while Predbat is stopped.
Keep automatic source updates disabled for this customised build. Start only
one controller instance and verify native-price freshness, a new plan,
controller health and the configured discharge floor before accepting it.
Keep the pre-deployment private backup until a restore has been tested.
