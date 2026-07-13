from src.data_ingestion import extract_historical_curves


def test_extract_historical_curves_shape_and_sanity():
    quotes = extract_historical_curves()

    assert len(quotes) > 0

    tenor_keys = [f"{tenor}Y" for tenor in range(1, 11)]
    for row in quotes:
        rate_keys = [key for key in row if key != "date"]
        assert len(rate_keys) == 10
        assert set(rate_keys) == set(tenor_keys)
        for key in tenor_keys:
            rate = row[key]
            assert rate is not None
            assert isinstance(rate, float)
            assert rate == rate  # not NaN

    # ~2 years of business days (roughly 252/year): flag rather than
    # silently accept a count wildly outside this, since BoE publishes a
    # fitted curve every business day and a bad count would mean a parsing
    # bug (e.g. holiday rows leaking through, or a bad date cutoff).
    assert 400 <= len(quotes) <= 520

    dates = [row["date"] for row in quotes]
    assert dates == sorted(dates)
    assert len(dates) == len(set(dates))
