"""EcoClaw entrypoint — starts energy proxy and carbon router together."""
import logging
import threading
import uvicorn

from . import state as st
from . import carbon_router
from . import proxy as _proxy
from .proxy import app, PROXY_PORT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def main():
    st.load_from_disk()

    # Create poll event and share it with the proxy for /demo/poll
    poll_event = threading.Event()
    _proxy.demo_poll_event = poll_event

    # Start carbon router in background thread
    router_thread = threading.Thread(
        target=carbon_router.run,
        kwargs={"initial_model_key": "nano", "poll_event": poll_event},
        daemon=True,
        name="carbon-router",
    )
    router_thread.start()
    log.info("Carbon router started")

    # Start energy proxy (blocks)
    log.info("Energy proxy starting on :%d", PROXY_PORT)
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)


if __name__ == "__main__":
    main()
