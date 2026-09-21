from argus.textutil import strip_emojis


def test_strip_emojis():
    assert strip_emojis("Hello 😀 world") == "Hello world"
    assert strip_emojis("No emoji here.") == "No emoji here."
    assert "👍" not in strip_emojis("Done 👍")
