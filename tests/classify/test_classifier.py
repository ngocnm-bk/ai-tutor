from ai_tutor.classify.classifier import classify_document


class FakeClaude:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def complete_json(self, **kw):
        self.calls += 1
        return self.result


def test_uses_heuristic_without_calling_claude():
    claude = FakeClaude({"lop": 9, "mon": "toan"})  # sẽ không được dùng
    c = classify_document("toan-lop3.mp4", "Bài 5 bảng nhân 6", claude)
    assert c.lop == 3 and c.mon == "toan" and c.source == "heuristic"
    assert claude.calls == 0  # tiết kiệm token: không gọi Claude


def test_falls_back_to_claude_when_heuristic_uncertain():
    claude = FakeClaude({"lop": 6, "mon": "tieng-anh", "bai": "Unit 3",
                         "ky_nang": ["present-simple"]})
    c = classify_document("ghichu.txt", "nội dung mơ hồ", claude)
    assert claude.calls == 1
    assert c.lop == 6 and c.mon == "tieng-anh" and c.bai == "Unit 3"
    assert c.ky_nang == ("present-simple",) and c.source == "claude"
    assert c.chuong is None


def test_returns_none_when_claude_response_unusable():
    """complete_json (JSON mode) có thể trả {} nếu Claude output không parse
    được (không còn ép schema qua tool call). classify_document phải degrade
    an toàn — trả None, không KeyError — để build_kb có thể bỏ qua và thử lại."""
    claude = FakeClaude({})
    c = classify_document("ghichu.txt", "nội dung mơ hồ", claude)
    assert claude.calls == 1
    assert c is None


def test_returns_none_when_claude_response_missing_lop_or_mon():
    claude = FakeClaude({"chuong": "Chương 1"})  # thiếu cả lop lẫn mon
    c = classify_document("ghichu.txt", "nội dung mơ hồ", claude)
    assert c is None
