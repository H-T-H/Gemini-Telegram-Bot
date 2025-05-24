import aiolimiter

# Telegram general soft limit is around 20-30 messages per second to one user,
# and bots can send to different users up to ~20 messages per minute in groups.
# The plan suggests 18 req/min, which is conservative and safe.
# 18 requests per 60 seconds.
limiter = aiolimiter.AsyncLimiter(max_rate=18, period=60)

# For very frequent stream updates, we might need a separate, more permissive limiter,
# or ensure that edit_message_text in streaming is handled carefully.
# The current streaming_update_interval is 0.5 seconds in config.py.
# 18/60 = 0.3 requests per second. This means one message every ~3.3 seconds.
# This rate is too slow for the streaming updates.
#
# Let's define two limiters:
# 1. A general limiter for most operations (18/min).
# 2. A more permissive limiter for streaming message edits (e.g., 1 per second, as edit_message_text has its own limits).
# Telegram allows editing messages more frequently than sending new ones, often up to 1 per second.

general_limiter = aiolimiter.AsyncLimiter(max_rate=18, period=60) # For most bot API calls
streaming_limiter = aiolimiter.AsyncLimiter(max_rate=1, period=1) # For bot.edit_message_text in streaming loops
