import logging

log = logging.getLogger(__name__)


async def fire_call(call):
    """Re-dispatch a captured call to its upstream server.

    Captured rows carry tool metadata, not routing info, so we only dispatch
    when the call has an explicit ``server`` and ``path``. Otherwise this is a
    no-op and the caller's "Firing request" log is the only record.
    """
    if not call.get("server") or not call.get("path"):
        log.info("no server/path for %s; nothing to dispatch", call.get("tool_name"))
        return

    from proxy.proxy import replay_call

    await replay_call(call)
