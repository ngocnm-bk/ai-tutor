from ai_tutor.tutor.prompts import build_system_prompt, NOT_REGISTERED_REPLY, NO_CONTEXT_REPLY


def test_system_prompt_grounding_and_lop():
    p = build_system_prompt(3)
    assert "3" in p
    low = p.lower()
    assert "tài liệu" in low  # ràng buộc grounding
    assert "cô" in low        # khuyên hỏi cô khi thiếu


def test_fallback_strings_nonempty():
    assert "dangky" in NOT_REGISTERED_REPLY.lower()
    assert len(NO_CONTEXT_REPLY) > 0
