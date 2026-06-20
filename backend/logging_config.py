import contextvars
import logging
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


def setup_logging(level: int = logging.INFO) -> None:
    fmt = "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s: %(message)s"
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def generate_request_id() -> str:
    return str(uuid.uuid4())[:8]
