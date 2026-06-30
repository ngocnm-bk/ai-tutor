from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.db import connect, init_db
from ai_tutor.claude_client import ClaudeClient
from ai_tutor.tutor.bot import build_application


def main() -> None:
    load_dotenv()
    cfg = load_config()
    conn = connect(cfg.db_path); init_db(conn)
    claude = ClaudeClient.from_config(cfg)
    app = build_application(cfg, conn, claude)
    print("AI Tutor bot đang chạy. Nhấn Ctrl+C để dừng.")
    app.run_polling()


if __name__ == "__main__":
    main()
