import collections
import logging

# Create a circular buffer for logs
MAX_LOG_ENTRIES = 500
log_buffer = collections.deque(maxlen=MAX_LOG_ENTRIES)


# Custom log handler to capture logs
class BufferLogHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        log_buffer.append(log_entry)


def setup_log_buffer():
    """Initialize and configure the log buffer"""
    # Add the buffer handler to the root logger
    buffer_handler = BufferLogHandler()
    buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(buffer_handler)

    return log_buffer


def get_logs(limit=50):
    """Get the most recent logs from the buffer"""
    return list(log_buffer)[-limit:]