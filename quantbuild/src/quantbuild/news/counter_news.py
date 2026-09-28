"""Counter-news detector for gold positions — checks if new headlines contradict open thesis."""
import logging
import re
from typing import Any

from src.quantbuild.models.news_event import NormalizedNewsEvent
from src.quantbuild.models.trade import Position

logger = logging.getLogger(__name__)

# Price words describe the subject of the headline. "Rise" is bullish gold only
# when the subject is gold; a rising dollar is bearish gold. They are ignored
# when the headline is about something else (oil, equities, a bank name).
_PRICE_BULL = {"surge", "rally", "rise", "jump", "soar", "gain", "higher", "bullish", "up"}
_PRICE_BEAR = {"fall", "crash", "drop", "decline", "plunge", "lower", "bearish", "down", "sell"}
_POLICY_BULL = {"cut", "dovish", "easing", "stimulus"}
_POLICY_BEAR = {"hike", "hawkish", "tightening", "tapering"}
_DOLLAR_WEAK = {"weaken"}
_DOLLAR_STRONG = {"strengthen"}
_GEO_BULL = {"war", "conflict", "escalation", "crisis"}
_GEO_BEAR = {"peace", "ceasefire", "de-escalation"}

_GOLD_SUBJECTS = (r"\bgold\b", r"\bbullion\b", r"\bxau(?:usd)?\b")
_DOLLAR_SUBJECTS = (r"\bdollars?\b", r"\bdxy\b", r"\bgreenback\b")
_RATE_SUBJECTS = (
    r"\bfed\b",
    r"\bfederal reserve\b",
    r"\bfomc\b",
    r"\brates?\b",
    r"\byields?\b",
    r"\btreasury\b",
    r"\bcpi\b",
    r"\binflation\b",
)


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Whole-word match plus a short inflection (rises, crashed, weakening)."""
    last = keyword[-1:]
    doubled = re.escape(last) + "?" if last.isalpha() and last not in "aeiou" else ""
    pattern = rf"\b{re.escape(keyword)}{doubled}(?:es|ed|ing|s)?\b"
    return re.search(pattern, text) is not None


def _hit_count(text: str, words: set[str]) -> int:
    return sum(1 for word in words if _keyword_in_text(word, text))


def _subject_present(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) is not None for pattern in patterns)


class CounterNewsDetector:
    def __init__(self, cfg: dict[str, Any]):
        counter_cfg = cfg.get("news", {}).get("counter_news", {})
        self._exit_threshold = counter_cfg.get("exit_threshold", 0.8)
        self._min_source_tier = 3

    def check_against_positions(
        self, event: NormalizedNewsEvent, positions: list[Position],
    ) -> list[dict]:
        """Returns list of affected positions with action recommendations."""
        affected = []
        for pos in positions:
            if not pos.thesis_valid:
                continue

            if not self._is_gold_related(event):
                continue

            contradiction_score = self._detect_contradiction(event, pos)
            if contradiction_score <= 0:
                continue

            source_authoritative = event.source_tier.value <= self._min_source_tier

            action = "exit" if (source_authoritative and contradiction_score >= self._exit_threshold) else "warn"

            affected.append({
                "trade_id": pos.trade_id,
                "direction": pos.direction,
                "contradiction_score": contradiction_score,
                "action": action,
                "reason": f"Counter-news from {event.source_name}: {event.headline[:80]}",
            })

            if action == "exit":
                logger.warning("THESIS INVALIDATED: %s by '%s'", pos.trade_id, event.headline[:60])
            else:
                logger.info("THESIS WEAKENED: %s by '%s'", pos.trade_id, event.headline[:60])

        return affected

    def _is_gold_related(self, event: NormalizedNewsEvent) -> bool:
        gold_topics = {"gold", "commodities", "macro", "central_banks", "dollar", "geopolitics"}
        if set(event.topic_hints) & gold_topics:
            return True
        lower = event.headline.lower()
        return any(kw in lower for kw in ["gold", "xau", "bullion", "fed", "rate", "dollar", "dxy"])

    def _detect_contradiction(self, event: NormalizedNewsEvent, position: Position) -> float:
        headline_lower = event.headline.lower()
        event_direction = self._get_gold_direction(headline_lower)
        if event_direction == "neutral":
            return 0.0

        pos_direction = "bullish" if position.direction == "LONG" else "bearish"

        if event_direction != pos_direction:
            base_score = 0.5
            if event.source_tier.value <= 2:
                base_score += 0.3
            return min(base_score, 1.0)
        return 0.0

    def _get_gold_direction(self, text: str) -> str:
        gold_subject = _subject_present(text, _GOLD_SUBJECTS)
        dollar_subject = _subject_present(text, _DOLLAR_SUBJECTS)
        rate_subject = _subject_present(text, _RATE_SUBJECTS)

        bull_hits = 0
        bear_hits = 0

        if gold_subject or dollar_subject:
            price_bull = _hit_count(text, _PRICE_BULL)
            price_bear = _hit_count(text, _PRICE_BEAR)
            # "Dollar rises" is bearish for gold. A gold subject keeps the
            # price words pointed at gold even if the dollar is also named.
            if dollar_subject and not gold_subject:
                price_bull, price_bear = price_bear, price_bull
            bull_hits += price_bull
            bear_hits += price_bear

        if dollar_subject:
            bull_hits += _hit_count(text, _DOLLAR_WEAK)
            bear_hits += _hit_count(text, _DOLLAR_STRONG)

        if rate_subject:
            bull_hits += _hit_count(text, _POLICY_BULL)
            bear_hits += _hit_count(text, _POLICY_BEAR)

        bull_hits += _hit_count(text, _GEO_BULL)
        bear_hits += _hit_count(text, _GEO_BEAR)
        if re.search(r"\brisk[\s-]+off\b", text):
            bull_hits += 1
        if re.search(r"\brisk[\s-]+on\b", text):
            bear_hits += 1

        if bull_hits > bear_hits:
            return "bullish"
        if bear_hits > bull_hits:
            return "bearish"
        return "neutral"
