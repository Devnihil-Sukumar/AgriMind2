"""
==========================================================================
AgriMind

Token Rate Limiter

Groq enforces a tokens-per-minute (TPM) allowance per model. The free
tier for openai/gpt-oss-120b is 8000 TPM, and the limiter counts the
prompt tokens PLUS the requested max_tokens for every call.

AgriMind issues several Groq calls inside one pipeline run, and the
Recommendation Agent and Explanation Engine fire back to back. Two
requests that each fit the allowance individually can still exceed it
within the same rolling minute, which surfaces as HTTP 429 or 413.

This limiter holds a rolling 60-second window of spent tokens and
blocks a request until enough budget has aged out, converting a hard
failure into bounded latency.

Author : AgriMind Team
==========================================================================
"""

import logging
import threading
import time
from collections import deque
from typing import Deque, Tuple

logger = logging.getLogger(__name__)


##########################################################################
# Rolling Window Token Limiter
##########################################################################

class TokenRateLimiter:

    """
    Thread-safe rolling-window token budget.
    """

    def __init__(
        self,
        tokens_per_minute: int,
        window_seconds: float = 60.0,
        name: str = "llm"
    ):

        self.tokens_per_minute = int(
            tokens_per_minute
        )

        self.window_seconds = float(
            window_seconds
        )

        self.name = name

        self._events: Deque[Tuple[float, int]] = deque()

        self._lock = threading.Lock()

    ####################################################################
    # Window Maintenance
    ####################################################################

    def _prune(
        self,
        now: float
    ) -> None:
        """
        Drop spend records that have aged out of the window.
        """

        cutoff = now - self.window_seconds

        while self._events and self._events[0][0] <= cutoff:

            self._events.popleft()

    def _spent(
        self,
        now: float
    ) -> int:
        """
        Tokens spent inside the current window.
        """

        self._prune(now)

        return sum(
            tokens
            for _, tokens in self._events
        )

    ####################################################################
    # Acquire
    ####################################################################

    def acquire(
        self,
        tokens: int,
        max_wait: float = 75.0
    ) -> float:
        """
        Reserve budget for a request, waiting if necessary.

        Returns the number of seconds spent waiting.

        A request larger than the whole allowance can never fit, so it
        is admitted immediately rather than blocked forever; the caller
        is expected to have applied a prompt budget already, and the
        provider error path handles the remainder.
        """

        if self.tokens_per_minute <= 0:

            return 0.0

        tokens = max(
            0,
            int(tokens)
        )

        waited = 0.0

        deadline = time.time() + max_wait

        while True:

            with self._lock:

                now = time.time()

                spent = self._spent(now)

                ####################################################
                # Fits
                ####################################################

                if spent + tokens <= self.tokens_per_minute:

                    self._events.append(
                        (now, tokens)
                    )

                    return waited

                ####################################################
                # Larger than the entire allowance
                ####################################################

                if tokens > self.tokens_per_minute:

                    logger.warning(
                        "%s request of %d tokens exceeds the whole "
                        "%d TPM allowance; sending anyway.",
                        self.name,
                        tokens,
                        self.tokens_per_minute
                    )

                    self._events.append(
                        (now, tokens)
                    )

                    return waited

                ####################################################
                # Wait for the oldest record to age out
                ####################################################

                oldest_at = self._events[0][0]

                sleep_for = max(
                    0.05,
                    (oldest_at + self.window_seconds) - now + 0.05
                )

            if time.time() + sleep_for > deadline:

                logger.warning(
                    "%s rate limiter wait exceeded %.0fs; sending "
                    "request without full budget.",
                    self.name,
                    max_wait
                )

                with self._lock:

                    self._events.append(
                        (time.time(), tokens)
                    )

                return waited

            logger.info(
                "%s rate limit: waiting %.1fs for token budget "
                "(spent=%d requested=%d limit=%d)",
                self.name,
                sleep_for,
                spent,
                tokens,
                self.tokens_per_minute
            )

            time.sleep(
                sleep_for
            )

            waited += sleep_for

    ####################################################################
    # Record
    ####################################################################

    def record(
        self,
        tokens: int
    ) -> None:
        """
        Record spend that was not reserved through acquire().
        """

        if self.tokens_per_minute <= 0:

            return

        with self._lock:

            self._events.append(
                (
                    time.time(),
                    max(0, int(tokens))
                )
            )

    ####################################################################
    # Introspection
    ####################################################################

    def remaining(self) -> int:
        """
        Tokens still available in the current window.
        """

        if self.tokens_per_minute <= 0:

            return self.tokens_per_minute

        with self._lock:

            return max(
                0,
                self.tokens_per_minute - self._spent(
                    time.time()
                )
            )
