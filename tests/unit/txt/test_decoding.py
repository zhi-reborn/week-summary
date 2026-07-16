import pytest

from app.infrastructure.txt.decoding import UnsupportedTextEncoding, decode_report


@pytest.mark.parametrize(
    ("data", "expected_encoding"),
    [
        ("姓名：张三\n完成A".encode("utf-8-sig"), "utf-8-sig"),
        ("姓名：张三\n完成A".encode("utf-8"), "utf-8"),
        ("姓名：张三\n完成A".encode("gb18030"), "gb18030"),
    ],
)
def test_decodes_supported_report_encodings(data: bytes, expected_encoding: str) -> None:
    result = decode_report(data)

    assert result.text == "姓名：张三\n完成A"
    assert result.encoding == expected_encoding


def test_rejects_binary_data() -> None:
    with pytest.raises(UnsupportedTextEncoding):
        decode_report(b"\x00\xff\x00\x81\x00\xfe")

