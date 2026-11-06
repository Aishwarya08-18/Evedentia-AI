# Pre-submission test checklist

- [ ] Fresh extraction into a new folder.
- [ ] `python -m pip install -r requirements.txt` succeeds.
- [ ] Server starts with `python server.py` and `/health` returns status `ok`.
- [ ] New account registration works.
- [ ] Duplicate username/email is rejected.
- [ ] Sign-in works with username and email.
- [ ] Unauthenticated dashboard/API access is blocked.
- [ ] Sample investigation is clearly labelled as built-in demo data.
- [ ] Upload investigation with two files reports exactly two sources.
- [ ] Upload investigation with three files reports exactly three sources.
- [ ] Auto-detect selects `order_id` for supplied demo CSVs.
- [ ] Evidence lists only values from the uploaded sources.
- [ ] A tie is flagged for human review rather than silently guessed.
- [ ] JSON report downloads and contains the investigation evidence.
- [ ] Do not use real customer or confidential business data in a public demo.
