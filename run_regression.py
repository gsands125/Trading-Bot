from master_router.replay import replay_personal_core640_exact

CSV = "/mnt/data/personal_v21_exact_rebuilt_core640_stream.csv"
r = replay_personal_core640_exact(CSV)

print("PERSONAL v2.1 EXACT REGRESSION")
print(f"Ending equity : ${r.ending_equity:,.2f}")
print(f"Peak equity   : ${r.peak_equity:,.2f}")
print(f"Trades taken  : {r.trades_taken}")
print(f"Signals skip  : {r.signals_skipped}")
print(f"Max EOD DD    : {100*r.max_eod_dd:.8f}%")

assert abs(r.ending_equity - 35583.64) < 1e-6
assert abs(r.peak_equity - 39006.82) < 1e-6
assert r.trades_taken == 458
assert r.signals_skipped == 182
assert abs(r.max_eod_dd - 0.3264484764398028) < 1e-12

r.event_log.to_csv(
    "/mnt/data/master_router_phase3_v0_1_personal_regression_log.csv",
    index=False
)
print("PASS — exact frozen benchmark reproduced.")
