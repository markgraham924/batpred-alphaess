# AlphaESS v9.0.2 release

This release merges upstream commit `bc853a0e` into the custom AlphaESS fork.
It preserves guarded Home Assistant control, the AlphaESS and towel plan
columns, published Optimise price boundaries and existing terminal energy value.
The experimental extended price forecast is not included or enabled.

## Regression baseline

The upstream random scenario baseline changes only for seeds 6 and 17.
The existing protection against moving force export into a Freeze Export slot
causes these differences. A Linux A/B replay removing only that guard in memory
restored all 320 upstream comparisons across all 20 scenarios. The custom
baseline therefore retains the guard and records its two different outcomes.
There was no production logic change to make the baseline pass.

Release checks run on Linux include the quick suite, all code quality hooks and
the 16 focused Optimise price coverage and horizon tests. Windows-only failures
in the Predheat timing and plugin startup tests do not reproduce on Linux.

## Deployment

Deploy the immutable custom release tag with its matching file manifest.
Back up code and configuration first, preserving credentials outside Git.
Restart only the Predbat app, retaining the controller enable settings.
Verify a fresh completed plan, controller health, price coverage and EV state.
Restore the backed-up runtime if startup or control verification fails.

## v9.0.2-alphaess.3 — deployed source alignment

This stable fork release captures the deployed seven-day planning context: E.ON supplies the executable day, followed by six days of Agile Predict context, with available Solcast P50 solar data. The 50% terminal reserve target and slot-aligned execution remain unchanged.

Release discovery, tagged downloads and startup verification now default to `markgraham924/batpred-alphaess`. Home Assistant links to the offered fork release, rather than an upstream URL containing a fork-only tag.

Validation: offline release-card, seven-day coverage, forecast, slot execution and terminal-target regressions pass. The GitNexus Windows runner failed during native dependency installation; direct call-site inspection and scoped diff review were used instead.

## v9.0.2-alphaess.4 - upstream clock fixes

Includes upstream main through `df6c4b9f`, with timezone-aware clock handling, the Solcast midnight race fix and upstream inverter fixes. Preserves the AlphaESS control guards, seven-day price context, 50% terminal target, slot scheduling and fork release discovery.

Published as a new immutable release so existing installations can identify the updated source correctly.
