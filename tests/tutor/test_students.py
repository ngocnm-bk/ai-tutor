from ai_tutor.db import connect, init_db
from ai_tutor.tutor.students import register_student, get_student


def _conn(tmp_path):
    c = connect(tmp_path / "t.db"); init_db(c); return c


def test_register_then_get(tmp_path):
    conn = _conn(tmp_path)
    assert get_student(conn, 111) is None
    register_student(conn, 111, "Bi", 3)
    row = get_student(conn, 111)
    assert row["name"] == "Bi" and row["lop"] == 3


def test_register_is_upsert(tmp_path):
    conn = _conn(tmp_path)
    register_student(conn, 111, "Bi", 3)
    register_student(conn, 111, "Bi", 6)  # đổi lớp
    assert get_student(conn, 111)["lop"] == 6
    n = conn.execute("SELECT COUNT(*) c FROM students").fetchone()["c"]
    assert n == 1
