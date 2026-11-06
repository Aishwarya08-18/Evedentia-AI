# EVEDENTIA AI — Explainable Business Data Investigation & Reconciliation

A local hackathon prototype that compares Sales, Inventory, Finance and other department exports; links records by a shared key; detects field-level conflicts; preserves source evidence; proposes policy-based resolutions; and flags unresolved ties for human review.

## Run on Windows / VS Code

1. Extract the ZIP.
2. In VS Code select **File → Open Folder** and open `EVEDENTIA_AI_RealWorld` (the folder containing `server.py`).
3. Open **Terminal → New Terminal** and run:

   ```powershell
   python -m pip install -r requirements.txt
   python server.py
   ```

4. Open `http://127.0.0.1:5000`.
5. Select **Create an account**, register, then sign in. There is no shared default password.

Alternatively, double-click `run_windows.bat` on Windows.

## Demo workflow

- For a quick built-in demo, use **Run sample investigation**. This deliberately uses built-in Sales, Inventory and Finance data.
- For a real upload test, upload two or more CSV/XLSX exports. The upload investigation uses only the files selected in that upload.
- The supplied test data is in `demo_data/`. Upload Sales.csv, Inventory.csv and Finance.csv together.
- Leave the matching key on **Auto-detect shared ID**; the supplied files share `order_id`.
- Optional example policy: choose Inventory for quantity and Finance for amount. Only configure source priority when that policy is appropriate for the business. Otherwise leave it blank.
- Review the evidence and proposed master data. Download the JSON report.

## What the workflow does

1. **Ingestion & Schema:** reads CSV/XLSX, normalizes common header aliases and retains observed fields.
2. **Record Linkage:** matches rows using a shared business key.
3. **Conflict Detection:** compares non-empty field values across sources.
4. **Evidence & Root-Cause:** displays source/value evidence and generates testable root-cause hypotheses.
5. **Resolution:** applies an explicitly configured source priority or an unambiguous majority; ties remain flagged for human review.

## Important truth-in-advertising / limitations

This is a local proof-of-concept, not a production enterprise platform. The five agents are deterministic, explainable Python workflow stages—not independent autonomous LLM agents. Root-cause explanations are hypotheses, not forensic proof. A source priority is a business policy, not an objectively discovered truth. The trust index is a heuristic indicator, not a calibrated probability. The app does not connect to live ERP/CRM systems or write corrections back to them. Always review proposed corrections before use.

For public production deployment, add HTTPS, a strong random `EVEDENTIA_AI_SECRET`, CSRF protection, rate limiting, role-based access, account recovery, persistent audit history, encryption, backups, malware scanning and a security review. Do not use real confidential customer data in a public hackathon demo.

## Submission materials

- `docs/HACKATHON_PITCH.md` — concise problem/solution pitch.
- `docs/DEMO_SCRIPT.md` — suggested live demo.
- `docs/TEST_CHECKLIST.md` — final test checklist.
