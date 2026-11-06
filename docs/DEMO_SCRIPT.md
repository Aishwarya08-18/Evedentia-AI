# 4-minute live demo

1. Start the local server and register a new user.
2. Sign in and show the dashboard.
3. Upload `demo_data/Sales.csv`, `demo_data/Inventory.csv`, and `demo_data/Finance.csv` together.
4. Leave matching key as **Auto-detect shared ID**. Confirm the result reports `order_id`.
5. Set quantity priority to Inventory and amount priority to Finance only for this demo. Explain that these are example business policies, not universal truths.
6. Run the investigation. Point out the ORD-1001 quantity disagreement (12 vs 10), amount disagreement (720000 vs 700000), and status differences.
7. Show evidence values by source and the proposed master record. Explain that root causes are hypotheses and proposed values require review.
8. Download the JSON report. Finish by explaining the human-in-the-loop and integration roadmap.

Do not claim the app connects to live enterprise systems or uses independent LLM agents. Be precise about what is implemented.
