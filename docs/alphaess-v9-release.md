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

## Portable local AlphaESS integration (v9.3.8-alphaess.6 candidate)

The portable path uses `templates/alphaess_local.yaml` with the separately
installed [AlphaESS Local v0.1.0-beta.1 prerelease](https://github.com/markgraham924/alphaess-local)
Home Assistant integration on HA 2026.10.1 or newer. It replaces the separate
Hillview Modbus YAML package and household controller scripts for this path.
The existing `AlphaESSController` inverter profile already provides the required
semantic service interface; no planner or existing household controller behaviour
was changed to add this installation example.

### Installation

1. Install the local integration and configure its inverter connection, model,
   capacity and power limits. Confirm its reported values match the installation.
   Keep its control switch off while completing setup.
2. Install the tested Predbat fork release from its GitHub repository. Keep
   Predbat read-only (`switch.predbat_set_read_only`) during setup.
3. Copy `templates/alphaess_local.yaml` into the Predbat `apps.yaml`. The default
   entity names assume the integration's device is named AlphaESS. Copy the
   actual IDs from Home Assistant if the names were changed or already existed.
4. Replace the fictional import/export tariff with your own rates and configure
   your own PV forecast. Remove `template: true` only once configured. For a lab,
   the fixture files below provide synthetic inputs instead.
5. Verify a completed plan and correct battery percentage, power-flow signs,
   capacity and reserve. The template reads capacity, effective export floor and power
   limits from integration entities. It has no fixed household battery size or
   power rating. The profile models one reserve floor, so the template uses
   the controller's effective export floor for both planning reserve settings.
   That conservatively keeps the export reserve in normal-demand forecasts too.
   Predbat's user reserve minimum may be set higher; the local integration
   independently refuses unsafe export targets and never changes the physical
   native reserve to follow a plan.
6. Stop competing inverter controllers. Enable local integration control and
   perform a short bounded charge/export/stop test. Confirm physical readback.
   Then remove Predbat read-only and select the intended control mode.
7. After an HA restart the integration requires control to be explicitly enabled
   again. Verify integration health and the new Predbat plan before resuming.

### Controller contract

`charge_start` and `discharge_start` receive `power` in watts, `target_soc` in
percent and a local `end_time`. Predbat's template substitutions send numeric
values as strings and time as `HH:MM:SS`; the integration validates and converts
those values. The controller owns the Modbus transaction and readback.

`discharge_freeze_service` maps to `mode19_start`. Mode 19 prevents PV charging,
exports surplus PV and can still allow battery discharge to supply household
load. It is not a zero-power forced-discharge command. `charge_stop` only stops
an owned charge; `discharge_stop` stops an owned export or Mode 19 request.
Both stop templates use `always: true`, ensuring repeated cancellations reach the
controller even when Predbat's previous service payload has not changed. The
controller must treat repeated inactive stops as no-ops.

Optional household AlphaESS plan-mode and towel display columns remain disabled
in the portable template. The household AlphaESS plan column currently uses
fixed household sensor names and a household soft floor; enabling that column
would not describe this installation correctly. Existing household configurations
and custom behaviour remain available unchanged.

### Account-free lab inputs

`fixtures/alphaess-lab-ha.yaml` provides a cumulative 500 W load forecast and
synthetic PV forecasts shaped like Home Assistant Solcast data. Merge it into the
lab HA configuration. If using `homeassistant.packages: !include_dir_named packages`,
copy it to `packages/alphaess_lab_fixtures.yaml`: HA package names require valid
slugs, so the installed package filename must use underscores rather than hyphens.
Copy `fixtures/alphaess-lab-predbat.yaml` keys under the
`pred_bat` section in the lab's copy of the template and remove `template: true`.
The tariff in the template has 5p overnight import and a 45p evening export
window. These prices are fictional test data, not an electricity offer.

First-day energy counters in a fresh integration contain only observed data;
there is no historic backfill. Use the synthetic load forecast in the lab rather
than treating those partial counters as a complete household history.

A meaningful release test must observe the planner choose charging when import
is cheap and export when export value is high, then trace the services through
HA to simulator register readback. Direct service calls and these contract tests
alone do not prove the full planning loop.

### Verification and licensing

The candidate passes 40 fork experiment tests, including four portable local
controller contract tests using the real `Inverter` implementation. It also
passes the focused inverter, execute, AlphaESS configuration, export encoding and
basic rate suites. Tests use different capacity, reserve and unequal charge and
discharge limits to detect household defaults. The grid sign test uses actual
inverter readings, aggregate publication and dashboard import/export icons:
the local integration reports positive import, while Predbat expects positive
export, so `grid_power_invert: true` is required. Logs are retained in the lab
workspace. Simulation does not establish compatibility with untested real
inverter models or firmware.

Predbat's original `License.md` is retained. It permits GitHub public forks and
contributions but limits use to personal non-commercial use in the UK and limits
distribution outside its GitHub repository. The separate local integration must
retain its own licence and Hillview attribution; including it does not relicense
Predbat. Publish the two repositories separately and link installation guidance.

To exercise both decisions immediately, run
`python fixtures/generate_alphaess_lab_scenarios.py --output /tmp/alphaess-lab`
in the isolated lab. It generates a cheap-import charge scenario and a high-value
export scenario covering only the current London half-hour. The charge phase has
a uniquely cheap -100p import rate; the export phase has a uniquely high 150p
export rate. Other slots retain 35p import and 0p export, so postponing an action
cannot obtain the same price. Regenerate before each phase and allow enough time
before the half-hour boundary for calculation and readback.
Both configurations retain read-only mode. Copy the selected file into the lab's
Predbat configuration, add the lab HA connection privately, and restart only the
lab Predbat process. For execution tests, enable the lab integration control,
turn `switch.predbat_set_read_only` off and select `Control charge & discharge`.
Keep `switch.predbat_set_charge_freeze` and `switch.predbat_set_export_freeze` off
for these tests. Start with mid-range simulator SoC so both directions have room.
After switching scenarios, request a fresh calculation with
`switch.predbat_active` and confirm a completed plan before judging readback.
The generator supplies fictional tariffs, never live supplier requests.

The integration's Predbat service aliases bind dispatch to planner health:
configure its planner prefix to match this template's `prefix` (default
`predbat`) and its status timeout (default 600 seconds). The status must be fresh
and error-free, read-only must be off, and the selected mode must allow the
requested action. Charge requires `Control charge` or `Control charge & discharge`;
export and Mode 19 require `Control charge & discharge`. The integration stops
and disarms when those conditions fail; a disconnected inverter instead falls
back to its bounded device lease. Manual integration actions deliberately use
separate ownership and are not cancelled by planner health changes.

When deliberately stopping Predbat, disable integration control or explicitly
stop its dispatch too rather than waiting for the stale-status timeout. Include
planner-loss, read-only and Monitor-mode cancellation in end-to-end commissioning
checks. Simulator success does not certify physical inverter lease enforcement.
