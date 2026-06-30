from dotenv import load_dotenv
from ai_tutor.config import load_config
from ai_tutor.tutor.bot import build_application


def main() -> None:
    load_dotenv()
    cfg = load_config()
    app = build_application(cfg)
    print("AI Tutor bot đang chạy. Nhấn Ctrl+C để dừng.")
    app.run_polling()


if __name__ == "__main__":
    main()
