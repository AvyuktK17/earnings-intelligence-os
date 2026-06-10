# Quality checklist — self-review before presenting the draft

Run through every item. If any fails, fix the draft before presenting it.

## Sourcing and grounding

- [ ] Every figure in the draft appears in the supplied report packet. Nothing
      came from memory, the web, another company, or another file.
- [ ] Every claim drawn from the packet's trusted claims cites its source
      reference and chunk id.
- [ ] Values the packet labelled "Not available" are reported as not available
      — never estimated, interpolated, or filled in.

## Prohibited content (must be entirely absent)

- [ ] No investment rating (Buy / Hold / Sell / Overweight / Underweight / etc.).
- [ ] No target price, fair value, or implied share price.
- [ ] No forecasts or forward estimates of any metric.
- [ ] No DCF, WACC, terminal value, or implied-value calculation.
- [ ] No consensus / "vs. Street" estimates.

## Honesty and labelling

- [ ] The document's first line is exactly:
      `Claude-assisted draft for analyst review`.
- [ ] Reported facts are clearly distinguished from analyst interpretation.
- [ ] Valuation data is labelled, every time it appears, as a dated, manually
      reviewed snapshot — not a live market feed.
- [ ] Thin or empty sections (e.g. no catalyst claims) say so plainly rather
      than being padded with invented content.

## Structure

- [ ] All 11 sections are present, in the order defined in `template.md`.
- [ ] The evidence appendix lets a reviewer trace each used claim back to the
      filing (claim id, accession, document key, chunk id, excerpt).
- [ ] The methodology/limitations section is present and accurate.

## Safety

- [ ] No API was called, no file was uploaded, and nothing was written to the
      database or any external service.
- [ ] The output is a local Markdown draft only.
