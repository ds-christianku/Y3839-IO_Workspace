# Market Symptom Evaluation
*Based on: market_symptom_analysis.md*  
*Total tickets analyzed: **9,785** (2025–2026)*

---

## Key Findings

### 1. Intermittent Connectivity is the #1 Field Issue
With **1,989 tickets (20.3%)**, connectivity/recognition failures dominate the ticket volume.
The problem is growing: **835 tickets in 2025 → 1,154 in 2026 (+38%)**.

> This aligns with the market feedback ("Intermittent Connectivity" + "Images not transferred" + "Loosening Screws" belong together as one failure pattern).

---

### 2. IOSS Performance / Slowness — Alarming 2026 Growth
**3rd Party Slowness: 681 tickets total**

| Year | Tickets | Change |
|------|--------:|--------|
| 2025 | 91 | baseline |
| 2026 | 590 | **+549%** |

This dramatic increase in 2026 suggests a **systemic issue introduced with a recent software/driver version** or a change in customer expectations. Highest priority for investigation.

---

### 3. "Dying Boxes" (USB Module Failures) — Steady Growth
**411 tickets total** — USB module hardware failures are consistently growing:

| Year | Tickets |
|------|--------:|
| 2025 | 174 |
| 2026 | 237 (+36%) |

Combined with "No Power" (349 tickets), the **Power/Module Failure group (760 tickets, 7.8%)** represents a relevant hardware reliability concern.

---

### 4. Images not transferred — Strong 2026 Spike
| Year | Tickets |
|------|--------:|
| 2025 | 97 |
| 2026 | 384 (+296%) |

The tripling in 2026 likely correlates with the IOSS / connectivity issues above.

---

### 5. Previous Patient Image (Ghost Image) — Emerging Trend
| Year | Tickets |
|------|--------:|
| 2025 | 26 |
| 2026 | 219 (+742%) |

A very strong increase — may be related to software update behavior or new firmware versions.

---

## Symptom Overview (Ranked by Volume)

| Rank | Symptom | Tickets | % | Trend |
|------|---------|--------:|--:|-------|
| 1 | Intermittent Connectivity | 1,989 | 20.3% | 📈 +38% |
| 2 | 3rd Party Slowness (NAM) | 681 | 7.0% | 🔴 +549% |
| 3 | "Dying Boxes" (USB module) | 411 | 4.2% | 📈 +36% |
| 4 | Images not transferred | 481 | 4.9% | 🔴 +296% |
| 5 | No Power | 349 | 3.6% | ➡️ stable |
| 6 | Previous (Patient) Image | 245 | 2.5% | 🔴 +742% |
| 7 | Interface Update Issues | 149 | 1.5% | ➡️ stable |
| 8 | Inconstant exposure signaling | 144 | 1.5% | 📈 +77% |
| 9 | White Images | 169 | 1.7% | ➡️ stable |
| 10 | Loosening Screws | 56 | 0.6% | ➡️ stable |
| 11 | Overexposed images | 14 | 0.1% | ➡️ stable |

---

## Action Priorities

| Priority | Symptom | Reason |
|----------|---------|--------|
| 🔴 **Critical** | 3rd Party Slowness | +549% in 2026 — possible software regression |
| 🔴 **Critical** | Previous Patient Image | +742% in 2026 — possible firmware behavior change |
| 🔴 **High** | Images not transferred | +296% in 2026 — linked to connectivity group |
| 🟡 **Medium** | Intermittent Connectivity | Largest absolute volume, steady growth |
| 🟡 **Medium** | "Dying Boxes" | Hardware reliability, steady increase |
| 🟢 **Monitor** | No Power, Interface Update, Loosening Screws | Stable, no alarming trend |

---

## Coverage Note

**4,688 of 9,785 tickets (47.9%)** were matched to a known market symptom.  
The remaining **5,097 tickets (52.1%)** fall into categories not covered by the current symptom list (e.g., Spare Parts/RMA, General User Info, Documentation).
