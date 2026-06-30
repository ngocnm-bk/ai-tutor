from ai_tutor.classify.heuristics import heuristic_classify
from ai_tutor.classify.types import Classification


def test_detects_lop_mon_chuong_bai_from_path_and_text():
    c = heuristic_classify("inbox/_processed/toan-lop3.mp4",
                           "Chương 2 - Phép nhân. Bài 5: Bảng nhân 6.")
    assert isinstance(c, Classification)
    assert c.lop == 3 and c.mon == "toan"
    assert c.chuong == "Chương 2" and c.bai == "Bài 5"
    assert c.ky_nang == () and c.source == "heuristic"


def test_detects_english_unit():
    c = heuristic_classify("baitap.docx", "Tiếng Anh lớp 6 - Unit 3: Present Simple")
    assert c.lop == 6 and c.mon == "tieng-anh" and c.bai == "Unit 3"


def test_returns_none_when_uncertain():
    assert heuristic_classify("ghichu.txt", "hôm nay học bài mới") is None
