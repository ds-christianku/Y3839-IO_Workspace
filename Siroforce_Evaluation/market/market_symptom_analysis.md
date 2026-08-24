# Market Symptom Analysis
*Generated: 2026-08-24*  
*Total tickets in dataset: **9,785***

---

## Group 1 — Connectivity / Sensor Recognition
**Group total: 2,526 tickets (25.8% of all tickets)**

| Symptom | Tickets | % of Total | Keywords (regex, in notes) |
|---------|--------:|-----------:|---------------------------|
| Intermittent Connectivity | 1,989 | 20.3% | `intermittent`, `not connect`, `not detect`, `not recogni`, `sensor not found`, `disconnect`, `no longer connect`, `loses connection`, `lost connection` |
| Images not transferred | 481 | 4.9% | `image not transfer`, `images not transfer`, `not acquiring`, `cannot capture`, `no image`, `unable to acquire`, `image.{0,20}not.{0,20}show`, `capture fail` |
| Loosening Screws | 56 | 0.6% | `screw.{0,20}loos`, `loos.{0,20}screw`, `loos.{0,20}screw`, `screw.{0,20}strip`, `strip.{0,20}screw`, `screw.{0,20}fall`, `loosening screw` |

<details>
<summary>Year breakdown for Group 1 — Connectivity / Sensor Recognition</summary>

| Symptom | 2025 | 2026 |
|---------|:---:|:---:|
| Intermittent Connectivity | 835 | 1154 |
| Images not transferred | 97 | 384 |
| Loosening Screws | 27 | 29 |

</details>

---

## Group 2 — Power / Module Failure
**Group total: 760 tickets (7.8% of all tickets)**

| Symptom | Tickets | % of Total | Keywords (regex, in notes) |
|---------|--------:|-----------:|---------------------------|
| "Dying Boxes" (USB module) | 411 | 4.2% | `dying box`, `usb module.{0,20}(fail|dead|replac|defect|broken|issue)`, `interface module.{0,20}(fail|dead|replac|defect|broken)`, `(2\.0|3\.0) remote.{0,20}(fail|dead|replac|defect|broken)`, `remote.{0,20}(fail|dead|replac|not.{0,10}work)`, `interface box.{0,20}(fail|dead|replac|defect)` |
| No Power | 349 | 3.6% | `no power`, `not power`, `dead on arrival` |

<details>
<summary>Year breakdown for Group 2 — Power / Module Failure</summary>

| Symptom | 2025 | 2026 |
|---------|:---:|:---:|
| "Dying Boxes" (USB module) | 174 | 237 |
| No Power | 166 | 183 |

</details>

---

## Other Symptoms
**Group total: 1,402 tickets (14.3% of all tickets)**

| Symptom | Tickets | % of Total | Keywords (regex, in notes) |
|---------|--------:|-----------:|---------------------------|
| White Images | 169 | 1.7% | `white image`, `all white`, `image.{0,20}white`, `white.{0,20}image`, `blank image`, `image without radiation` |
| Overexposed images | 14 | 0.1% | `overexpos`, `over.expos`, `too bright`, `overexposure`, `recommended generator setting`, `generator setting.{0,30}overexpos` |
| Previous (Patient) Image | 245 | 2.5% | `previous.{0,20}image`, `patient.{0,20}image`, `old image`, `prior image`, `last patient`, `ghost image` |
| Interface Update Issues | 149 | 1.5% | `interface update`, `firmware update`, `update.{0,20}fail`, `update.{0,20}issue` |
| Inconstant ready-for-exposure signaling (SW vs. Interface) | 144 | 1.5% | `ready.for.exposure`, `not ready`, `timing out`, `exposure signal`, `ready signal`, `inconstant.{0,20}signal`, `(sw|software).{0,20}(vs|versus).{0,20}interface` |
| 3rd Party Slowness (NAM) | 681 | 7.0% | `slow`, `slowness`, `latency`, `lag`, `performance`, `takes .{0,20}seconds`, `wait until` |

<details>
<summary>Year breakdown for Other Symptoms</summary>

| Symptom | 2025 | 2026 |
|---------|:---:|:---:|
| White Images | 82 | 87 |
| Overexposed images | 8 | 6 |
| Previous (Patient) Image | 26 | 219 |
| Interface Update Issues | 70 | 79 |
| Inconstant ready-for-exposure signaling (SW vs. Interface) | 52 | 92 |
| 3rd Party Slowness (NAM) | 91 | 590 |

</details>

---

## Overall Summary

| Symptom | Tickets | % of Total |
|---------|--------:|-----------:|
| Intermittent Connectivity | 1,989 | 20.3% |
| Images not transferred | 481 | 4.9% |
| Loosening Screws | 56 | 0.6% |
| "Dying Boxes" (USB module) | 411 | 4.2% |
| No Power | 349 | 3.6% |
| White Images | 169 | 1.7% |
| Overexposed images | 14 | 0.1% |
| Previous (Patient) Image | 245 | 2.5% |
| Interface Update Issues | 149 | 1.5% |
| Inconstant ready-for-exposure signaling (SW vs. Interface) | 144 | 1.5% |
| 3rd Party Slowness (NAM) | 681 | 7.0% |
| **Total (mapped)** | **4,688** | **47.9%** |
| *Total tickets in dataset* | *9,785* | *100%* |

---

## Notes

- Matching is based on **keyword search in `notes_text`** (full ticket notes, case-insensitive regex).
- A ticket may match multiple symptoms if the notes contain keywords for several symptoms.
- The keyword patterns use regular expressions (case-insensitive).