# Predbat

This is Mark's AlphaESS fork. The `v9.3.8-alphaess.5` candidate incorporates
upstream main through `1faff228` (13 October 2026), while retaining the deployed
custom behaviour. The custom suffix distinguishes this build from upstream.

The guarded `AlphaESSController` Home Assistant integration remains the owner of
inverter commands. The BMW/OCPP Home Assistant package remains the charger owner.
Supplier control must not be enabled as a side effect of an upstream merge.

The retained patches cover native E.ON Optimise prices and coverage guards;
published-price execution boundaries; bounded future battery valuation;
seven-day forecast context with an optional terminal target; slot-aligned
planning and execution checks; fixed EV overrides; solar/export preferences;
explicit freeze at full charge; high-SOC Mode 19 removal; AlphaESS charge and
discharge limit annotations; towel and EV history; car end-of-period SOC;
appliance cost scenarios; usable-capacity chart corrections; Kraken coverage
metadata; the dormant proxy helper; and this fork's update source.

Estimated forecast rows influence boundary valuation but are not executable
windows. The 50% continuation target is separate from the controller's 9%
forced-export soft floor and at least 6% household protection. An armed expired
EV override remains paused until explicitly cancelled.

Compatibility regressions run from `coverage` with
`python -m unittest discover -s ../experiments -p 'test_*.py'`, alongside the
normal quick suite and kernel parity tests. The fork's random-plan baseline
deliberately differs in scenarios 6 and 17: protecting a freeze destination from
export swaps retains the owner's solar-routing preference. A control with only
that guard removed matches all 20 upstream scenarios across 320 fields.

![image](https://github.com/springfall2008/batpred/actions/workflows/code-quality.yml/badge.svg)
![image](https://github.com/springfall2008/batpred/actions/workflows/publish-docs.yml/badge.svg)
![image](https://github.com/springfall2008/batpred/actions/workflows/pages/pages-build-deployment/badge.svg)

## Introduction

Home battery prediction and automatic charging for Home Assistant supporting multiple inverters, including GivEnergy, Solis, Huawei, SolarEdge, SigEnergy, FoxESS, Sofar, Tesla Powerwall and many more.

Also known by some as Batpred or Batman!

![icon](https://github.com/springfall2008/batpred/assets/48591903/7c207423-1423-4f88-beb2-d1da5cfbfeeb) ![image](https://github.com/springfall2008/batpred/assets/48591903/e98a0720-d2cf-4b71-94ab-97fe09b3cee1)

If you want to buy me a beer, then please use [Paypal](https://paypal.me/predbat?country.x=GB&locale.x=en_GB) or [GitHub sponsor](https://github.com/springfall2008)
![image](https://github.com/springfall2008/batpred/assets/48591903/b3a533ef-0862-4e0b-b272-30e254f58467)

* Use my referral code for Octopus Energy: <https://share.octopus.energy/jolly-eel-176>
* Use my referral code for Axle Energy (UK): <https://vpp.axle.energy/landing/grid?ref=R-VWIICRSA>

If you find Home Assistant and Predbat too difficult to set up yourself, there is now [PredBat Cloud](https://predbat.com/), a paid version of Predbat hosted in the cloud. Please note that while I have given permission for PredBat Cloud to operate under license, PredBat will remain open source for personal use.

## Predbat documentation

You can find the latest Predbat documentation at [https://springfall2008.github.io/batpred/](https://springfall2008.github.io/batpred/) and
how-to videos on my [YouTube channel](https://www.youtube.com/@springfall2008).

The documentation covers how Predbat works and how to get it installed
and configured, video tutorials and FAQs to help you get going.
It also explains how you can contribute to the project.

## Support

For support, please raise a GitHub ticket or use the Facebook Group: [Predbat](https://www.facebook.com/groups/1477599886299106)

Some inverters have their own groups also, e.g.:

* [GivTCP](https://www.facebook.com/groups/615579009972782)
* [Solis](https://www.facebook.com/groups/288045168816481)

## License

Please see [License](https://github.com/springfall2008/batpred/blob/main/License.md)

```text
Copyright (c) Trefor Southwell 2025-2026 - All rights reserved
This software may be used at no cost for personal use only.
No warranty is given, either expressed or implied.
```
