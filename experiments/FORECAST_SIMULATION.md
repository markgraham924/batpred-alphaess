# Forecast simulation in the main plan

The published-price plan remains the only executable plan (maximum 24 hours when the trial is enabled). Up to 36 additional hours are evaluated by a finite battery-state dynamic programme. Its continuation value is included when Predbat ranks near-term candidates, so future demand and refill opportunities affect today's decisions without speculative tariff entries reaching dispatch.

The displayed continuation starts at the selected plan's exact final battery energy and metered cost. It shows nominal simulated modes, SoC and running costs in the same web table. Those rows are stored separately as `forecast_simulation`, have no override controls, and never enter charge/export window arrays. History does not include them.

Valuation blends 75% nominal and 25% lower solar (30% reduction) with an extra 2 kWh household demand. These are judgement-based scenarios, not calibrated confidence probabilities. The displayed path is nominal, not a promise that future actions or costs will occur.

Limits and caveats:

- Configured reserve, capacity, battery power, shared inverter output and export limits apply. The AC approximation uses conservative combined efficiency and the existing cycling penalty; it is not the full near-term inverter kernel, including its SoC-dependent taper.
- External household load forecasts take precedence. Beyond their coverage, their last complete daily profile repeats; future vehicle arrivals or towel demands are not invented. PV coverage must remain contiguous.
- No value is assigned after the final forecast row. The final day is therefore still a finite-horizon approximation.
- Missing, stale or invalid context falls back to the existing useful-energy valuation. Merely moving closer in time does not turn estimates into confirmed prices: supplier coverage must actually arrive.
- The current HA source is still the explicitly timestamped trial snapshot, not an automatically refreshed production feed. Its six-hour freshness limit is unchanged.

Regression coverage includes a real-household replay, the exact boundary join, positive/negative tariffs, expensive/cheap refill, extra demand, high PV, partial slots, reserve/power/export constraints, external-load wrapping and non-editable web rendering.
