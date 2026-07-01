from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.llm import LLMClient
from ai_tutor.kb.build import build_kb


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    llm = LLMClient.from_config(cfg)
    report = build_kb(cfg, conn, llm)
    print(f"Phân loại: {report.classified} | Bài đụng tới: {report.lessons_touched} "
          f"| Tổng hợp mới: {report.synthesized}")


if __name__ == "__main__":
    main()
