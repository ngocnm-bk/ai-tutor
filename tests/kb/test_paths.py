from pathlib import Path
from ai_tutor.kb.paths import slugify, lesson_dir
from ai_tutor.classify.types import Classification


def test_slugify_strips_vietnamese_accents():
    assert slugify("Chương 2 - Phép nhân") == "chuong-2-phep-nhan"
    assert slugify("Bài 5: Bảng nhân 6") == "bai-5-bang-nhan-6"
    assert slugify("đặt đúng") == "dat-dung"
    assert slugify("") == "khac"


def test_lesson_dir_layout():
    c = Classification(lop=3, mon="toan", chuong="Chương 2", bai="Bài 5",
                       ky_nang=(), source="heuristic")
    p = lesson_dir(Path("/kb"), c)
    assert p == Path("/kb/toan/lop3/chuong-2/bai-5")


def test_lesson_dir_none_chuong_bai_uses_khac():
    c = Classification(lop=6, mon="tieng-anh", chuong=None, bai=None,
                       ky_nang=(), source="claude")
    p = lesson_dir(Path("/kb"), c)
    assert p == Path("/kb/tieng-anh/lop6/khac/khac")
