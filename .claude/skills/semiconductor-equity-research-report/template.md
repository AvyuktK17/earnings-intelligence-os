# Report template — semiconductor earnings update

Produce the draft in this exact section order. Begin the document with the
mandatory label line, then the title.

```
Claude-assisted draft for analyst review

# {Company Name} ({TICKER}) — Earnings Update
```

Then a short metadata block drawn from the packet (filing form, accession
number, filing date, business model, and the valuation snapshot date with the
"dated, manually reviewed snapshot — not a live market feed" caveat).

---

## 1. Front-page executive summary

A concise (3–6 sentence) thesis-style summary of the quarter, built only from
packet facts. Lead with the reported headline figures (revenue and growth,
margins, EPS). You may add one or two sentences of interpretation, clearly
marked as interpretation. **No rating, no target price, no forecast.**

## 2. Quarterly results analysis

Walk through the reported financial snapshot: revenue and YoY growth, gross
profit and margin, operating income and margin, net income, diluted EPS, R&D
spend and intensity. Quote reported numbers from the packet. Where a trusted
claim adds colour, cite it with its source reference and chunk id. Mark
interpretation separately from reported figures.

## 3. Guidance and outlook

Summarise only guidance/outlook that appears in the packet's trusted claims
(routed from human-reviewed claim text). **Do not produce your own forecasts or
estimates.** If the packet contains no guidance claims, state that explicitly.

## 4. Historical operating trends

Describe the multi-period trend table (revenue, gross margin, operating margin,
FCF margin) from the packet. Note direction and magnitude of changes using only
the supplied periods/values. Label any period marked "Not available" honestly.

## 5. Peer comparison

Summarise the peer-comparison table: where the subject company sits on revenue,
growth, margins, EV/TTM revenue, and FCF yield relative to peers. Repeat the
caveat that multiples use a dated snapshot and that debt measures differ across
issuers (indicative, not strictly like-for-like).

## 6. Balance sheet and free-cash-flow discussion

Cover cash, total debt, net cash/(debt), operating cash flow, capex, free cash
flow, and TTM FCF from the packet. Discuss balance-sheet strength and cash
generation using only reported figures. Mark interpretation separately.

## 7. Valuation snapshot

Present the valuation snapshot: snapshot date, share price, market cap,
enterprise value, and the deterministically computed multiples (EV/TTM revenue,
EV/TTM operating income, price/TTM FCF, FCF yield). **Every time**, label this
as a dated, manually reviewed snapshot, not a live market feed. **No target
price, no rating, no DCF, no fair-value estimate.**

## 8. Catalysts

List catalysts only where supported by the packet's trusted claims; cite each
with its source reference and chunk id. If none are supported, say so. Do not
invent catalysts or forward-looking projections.

## 9. Risks and watch items

List risks/watch items supported by the packet's trusted claims, with citations.
You may add neutral, fact-based watch items derived strictly from reported
figures (e.g. an observed margin decline), clearly marked as interpretation. Do
not invent risks.

## 10. Evidence appendix

Reproduce the evidence trail: for each trusted claim used, list the claim id,
accession number, document key, and source chunk id, plus the supporting
excerpt. This lets a human reviewer trace every claim back to the filing.

## 11. Methodology and limitations

State plainly that:

- this is a Claude-assisted draft for analyst review, not human-reviewed or
  published;
- it was drafted only from a deterministic report packet of trusted claims and
  audited figures;
- it contains no forecasts, DCF values, price targets, ratings, or consensus
  estimates;
- valuation is a dated, manually reviewed snapshot, not a live feed;
- missing inputs are labelled rather than estimated;
- peer multiples are indicative rather than strictly like-for-like.
