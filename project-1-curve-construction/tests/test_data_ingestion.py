from src.data_ingestion import extract_quotes


def test_extract_quotes_shape_and_sanity():
    quotes = extract_quotes()

    assert len(quotes) == 10

    tenors = [tenor for tenor, _ in quotes]
    assert tenors == [float(n) for n in range(1, 11)]

    for _, rate in quotes:
        assert isinstance(rate, float)
        assert rate > 0.0
        assert rate < 0.20
