from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.llm import LLMClient
from ai_tutor.ingest.pipeline import ingest_once, build_default_extractors


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    llm = LLMClient.from_config(cfg)
    report = ingest_once(cfg, conn, extractors=build_default_extractors(llm))
    print(f"Đã nạp: {report.ingested} | Bỏ qua (trùng): {report.skipped} | "
          f"Lỗi: {report.failed} {report.failed_files}")


if __name__ == "__main__":
    main()
