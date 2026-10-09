# Renewal Build (Django service)

Turns a carrier's renewal packet into the Clasp API calls that build the new
plan year and its open enrollment.

```
packet (PDF / .xlsx)
  -> read          layout parser for known layouts, Claude for anything else
  -> validate      DRF serializers (same contract for every reader)
  -> ground        every value found where the reader says it's printed
  -> check         age curve, completeness, dates and plans vs. Clasp, PA filings
  -> review        a person fixes or keeps each flag, confirms plan mapping
  -> build         POST /plans, /plans/{id}/premiums, /plan_configurations,
                   /open_enrollment_windows, validated against Clasp's request schemas
```

AI reads the documents; plain code verifies the numbers; a person approves.
Nothing is sent to Clasp: the output is the ordered list of calls.

## Run it

```bash
pip install -e ".[dev]"
python build_service/manage.py runserver 8001        # standalone, at /api/build/...
uvicorn api.index:app --port 8000                     # or mounted inside the FastAPI app
pytest                                                 # includes build_service/tests
python scripts/make_renewal_packets.py                 # regenerate the sample packets
```

Set `ANTHROPIC_API_KEY` to read packets with Claude (and `ANTHROPIC_MODEL` to
pick the model). Without it, only the sample "Carrier A" layout can be read.

## Layout

| Path | What |
| --- | --- |
| `renewals/services/layout_parser.py` | Deterministic reader for the sample carrier's PDF and spreadsheet layout |
| `renewals/services/claude_extractor.py` | Forced tool use: Claude fills a strict schema, quoting where each value is printed |
| `renewals/services/extract.py` | Format detection, grounding, page previews |
| `renewals/services/checks.py` | The rules: age curve, missing ages, dates, plan mapping, current rates, filings |
| `renewals/services/clasp_requests.py` | Approved packet -> Clasp requests, validated with `jsonschema` |
| `renewals/services/preview.py` | Runs the reviewed rates through the Renewal Advisor engine |
| `renewals/serializers.py`, `views.py` | DRF contract and endpoints |
| `clasp_schema/requests.json` | Request schemas transcribed from Clasp's API reference (2026-04-24) |

## Known limits / next steps

- Stateless: nothing is saved. Next: Postgres models for packets, review
  decisions (who kept what, when) and builds.
- Clasp-side context comes from the sample groups. Live: read the group, its
  plans, current plan configuration and open enrollment window from Clasp's API,
  and send the calls with a sandbox key.
- Request schemas are transcribed; swap in Clasp's published `schema.yaml`.
- Checks assume the federal default age curve (flagged for states that differ).
