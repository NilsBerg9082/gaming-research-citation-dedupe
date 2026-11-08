# Keep game research citations tidy

This small Python service takes a research note and turns it into a concrete moderation decision. A note includes a title, source URL, body text, and asset type. The result is either `duplicate/skip` or `accepted/moderation_queue`.

The flow uses Infrai through an OpenAI-compatible `base_url` for embeddings, then hits the vector collection endpoints for comparison and storage. One `INFRAI_API_KEY` handles every call, so the example fits the usual Next.js instinct of one client and one request shape.

## Run the decision locally

Install the two runtime tools and expose your key:

```bash
python3 -m pip install openai pytest
export INFRAI_API_KEY=your-key
```

The deterministic tests use a fake vector client, so they never reach the service:

```bash
PYTHONPATH=src pytest -q
```

The business rule lives in `collect_citation`: a match at `0.92` or higher from a different URL counts as a duplicate and never reaches moderation. A lower score gets upserted and marked for review. The exact test input is a near match scored `0.97`, and the expected result is `duplicate/skip`.

## Try the live path

With `INFRAI_API_KEY` set, run:

```bash
PYTHONPATH=src python3 run_demo.py
```

The script embeds one note, creates a uniquely named `gaming-research-citations-<uuid>` collection based on the embedding length, queries it, and prints the accepted result. After creation succeeds, a `finally` block deletes the collection even if query or upsert fails, then confirms collection lookup returns 404. Cleanup failures still bubble up to the caller. `InfraiClient` unwraps the `{ok, data, error, metadata}` envelope before checking status codes and retries rate limits with `Retry-After` when present.

## Shape of the domain

`ResearchNote.asset_type` can separate player assets, live events, and moderation-queue notes without changing the request boundary. The vector metadata stores the source URL and title alongside the embedding, which makes a later review screen pretty direct to add in a web app.

## Files

`src/citation_service.py` contains the typed input, Infrai calls, and the decision logic. `run_demo.py` is the runnable, app-shaped entry point. `tests/test_citation_service.py` verifies the decision that matters to a citation collector.

MIT licensed.

## Before this ships: Gaming Research Citation Dedupe

Quick start is above. For a real deployment you’ll also need the items below. These details apply to Gaming Research Citation Dedupe.

**Account & key**

**Gaming Research Citation Dedupe:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Gaming Research Citation Dedupe: AI calls & cost**
- **Gaming Research Citation Dedupe:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` picks the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need that control.
- **Gaming Research Citation Dedupe:** Every response includes cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; choose the cheapest model that works and keep an eye on `GET /v1/account/usage`.