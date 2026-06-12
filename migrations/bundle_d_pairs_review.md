# Bundle D — Pair review (v1 approved shortlist)

27 candidates reviewed 2026-06-12. Outcome: 15 active v1 pairs, 9 holdouts,
3 dropped. Only the 15 active pairs will be inserted with
`manually_reviewed = true`.

---

## v1 active pairs (15) — insert with `add_screen_pairs.py --confirm`

### AVGO — 4 pairs

| Target | Fit note | Regulatory flag |
|---|---|---|
| CRDO | High-speed SerDes/AEC connectivity adjacent to Tomahawk/Jericho networking | China revenue exposure both sides |
| ALAB | AI-cloud retimers/CXL extends data-center franchise | Deal-size scrutiny in AI infra |
| MTSI | RF/photonics components complement optical networking | Low |
| RMBS | Memory-interface chips and silicon IP licensing fits AVGO's IP economics | Low |

### NVDA — 2 pairs

| Target | Fit note | Regulatory flag |
|---|---|---|
| ALAB | Connectivity for AI servers — direct ecosystem adjacency | High: NVDA deals draw global review post-ARM |
| CRDO | AECs/optical DSP in AI clusters complement NVLink/Ethernet strategy | High: NVDA deals draw global review post-ARM |

### AMD — 4 pairs

| Target | Fit note | Regulatory flag |
|---|---|---|
| LSCC | Low-power FPGA complements Xilinx high-end line (Xilinx playbook continuation) | China approval risk (Xilinx precedent: cleared) |
| ALAB | AI-platform connectivity for Instinct scale-out | Moderate |
| CRDO | SerDes/connectivity tightens AMD data-center GPU stack | Moderate |
| RMBS | Memory-interface IP relevant to HBM-heavy roadmap | Low |

### QCOM — 4 pairs

| Target | Fit note | Regulatory flag |
|---|---|---|
| SYNA | IoT/edge connectivity directly overlaps QCOM diversification push | China approval risk (NXP precedent: blocked) |
| SLAB | IoT wireless SoC strengthens connected-device franchise | China approval risk (NXP-pattern) |
| ALGM | Auto magnetic sensing accelerates automotive ambitions | Auto-supplier review likely |
| AMBA | Vision SoC for ADAS/IoT cameras strengthens QCOM ADAS narrative | Moderate |

### INTC — 1 pair

| Target | Fit note | Regulatory flag |
|---|---|---|
| MTSI | Photonics aligns with INTC silicon-photonics strategy and optical interconnect roadmap | Low |

---

## Holdouts (9) — not inserted in v1; revisit after first scoring run

| Acquirer | Target | Reason held |
|---|---|---|
| AVGO | MXL | Financial volatility; affordability may mask quality issues |
| AVGO | SMTC | LoRa is a weak strategic fit for AVGO's infra thesis |
| NVDA | SITM | Timing is a commodity adjacent; strategic fit is thin |
| NVDA | AMBA | Post-ARM scrutiny makes any NVDA deal high-risk at this size |
| NVDA | MTSI | Post-ARM scrutiny; marginal photonics fit for NVDA |
| AMD | AMBA | AMD/embedded fit weaker post-Xilinx integration challenges |
| QCOM | CRUS | AAPL customer-concentration risk makes fit awkward for QCOM |
| QCOM | POWI | Too tangential to QCOM's stated automotive/IoT vectors |
| INTC | RMBS | IP overlap with existing INTC assets; duplication risk |

---

## Dropped (3) — excluded from all versions of the screen

| Acquirer | Target | Reason dropped |
|---|---|---|
| QCOM | SITM | Too small and tangential; timing is not a strategic gap for QCOM |
| INTC | SITM | Balance-sheet constrained; fit is superficial |
| INTC | LSCC | INTC already owns Altera; LSCC adds overlap and antitrust questions |

---

## Notes

* INTC's single pair and constrained capacity are a *feature* of the screen —
  the affordability component should visibly score it low, demonstrating the
  model works correctly on weak-capacity acquirers.
* The capacity model is cash-based and ignores stock-funded deals (AMD/Xilinx
  was all-stock) — documented as a known limitation, not silently wrong.
* `manually_reviewed = true` is set only on the 15 v1 active pairs. Holdouts
  are not inserted; they can be added individually after review.
