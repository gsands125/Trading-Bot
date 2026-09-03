from master_router.replay import replay_personal_core640_exact

def test_exact_personal_v21():
    r = replay_personal_core640_exact(
        "/mnt/data/personal_v21_exact_rebuilt_core640_stream.csv"
    )
    assert abs(r.ending_equity - 35583.64) < 1e-6
    assert abs(r.peak_equity - 39006.82) < 1e-6
    assert r.trades_taken == 458
    assert r.signals_skipped == 182
    assert abs(r.max_eod_dd - 0.3264484764398028) < 1e-12
