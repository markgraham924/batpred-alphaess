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
