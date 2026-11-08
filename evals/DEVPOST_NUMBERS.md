We ran the sealed test once with frozen model 67fe7df and data SHA-256 c20095a240dc38423d3a3c9e90ac36c597215128d6b39ed4fb5f9e143d86b910.
Calls and account events use the hybrid model plus rules: it caught 30 of 30 coached cases (rules-only: 21 of 30) and was the only tested scorer to catch bots (12 of 12; rules-only: 0 of 12).
Forwarded texts use rules: they caught 28 of 30 scam texts (hybrid: 6 of 30), with no false positives on the six benign texts for either scorer.
We chose this routing after seeing the sealed results (D-060); we claim no combined sealed score and did not score the routed system on the sealed set.
Dev-split numbers remain "test-informed during development"; all data are synthetic, so we make no real-carrier performance claim.
