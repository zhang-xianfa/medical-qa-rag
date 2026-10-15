"""
# =============================================================================
# PII 检测与脱敏引擎
#
# 所有用户输入在进入 AI 推理前，必须先经本模块脱敏处理。
# 支持 6 类 PII：姓名、身份证号、手机号、邮箱、地址、银行卡号。
# 优先使用 presidio-analyzer（如已安装），降级使用内置正则。
# =============================================================================
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PIIMatch:
    type: str
    start: int
    end: int
    original: str
    masked: str


@dataclass
class PIIResult:
    masked_text: str
    matches: list[PIIMatch] = field(default_factory=list)

    @property
    def detected_types(self) -> set[str]:
        return {m.type for m in self.matches}

    @property
    def count(self) -> int:
        return len(self.matches)


class PIIDetector:
    """
    PII 检测与脱敏引擎。

    优先尝试 presidio-analyzer（需 pip install presidio-analyzer），
    不可用时自动降级为内置正则，保证零外部依赖也能运行。
    """

    TYPES: dict[str, dict] = {
        "PERSON": {
            "label": "姓名",
            "regex": r"(?:我叫|我是|本人|姓名[:：]?|患者[:：]?|联系人[:：]?)\s*([一-鿿]{2,4})",
            "replacement": "[姓名]",
        },
        "ID_CARD": {
            "label": "身份证号",
            "regex": r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)",
            "replacement": "[身份证号]",
        },
        "PHONE_NUMBER": {
            "label": "手机号",
            "regex": r"(?<!\d)1[3-9]\d{9}(?!\d)",
            "replacement": "[手机号]",
        },
        "EMAIL_ADDRESS": {
            "label": "邮箱",
            "regex": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "replacement": "[邮箱]",
        },
        "ADDRESS": {
            "label": "地址",
            "regex": r"(?:地址[:：]?|住址[:：]?|位于|在)([一-鿿]{3,}(?:省|市|区|县|镇|乡|街道|路|巷|号|楼|单元|层|室|栋))[一-鿿\d]*(?:省|市|区|县|镇|乡|街道|路|巷|号|楼|单元|层|室|栋)?",
            "replacement": "[地址]",
        },
        "BANK_ACCOUNT": {
            "label": "银行卡号",
            "regex": r"(?<!\d)(?:62\d{14,17})(?!\d)",
            "replacement": "[银行卡号]",
        },
    }

    TYPE_ORDER = ["ID_CARD", "BANK_ACCOUNT", "PHONE_NUMBER", "EMAIL_ADDRESS", "PERSON", "ADDRESS"]

    def __init__(self, enabled_types: list[str] | None = None) -> None:
        enabled = set(enabled_types or self.TYPES.keys())
        self._rules = {k: v for k, v in self.TYPES.items() if k in enabled}
        self._compiled: dict[str, re.Pattern] = {
            k: re.compile(v["regex"]) for k, v in self._rules.items()
        }
        self._presidio = None
        self._try_load_presidio()

    def _try_load_presidio(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine
            self._presidio = AnalyzerEngine()
            logger.info("presidio-analyzer loaded, using NER-enhanced PII detection")
        except ImportError:
            logger.info("presidio-analyzer not installed, using regex-only PII detection")

    def detect_and_mask(self, text: str) -> PIIResult:
        if self._presidio is not None:
            return self._mask_with_presidio(text)
        return self._mask_with_regex(text)

    def _mask_with_regex(self, text: str) -> PIIResult:
        raw_matches: list[PIIMatch] = []
        ordered_types = [t for t in self.TYPE_ORDER if t in self._rules]
        for pii_type in ordered_types:
            rule = self._rules[pii_type]
            pattern = self._compiled[pii_type]
            for m in pattern.finditer(text):
                original = m.group(0)
                if pii_type == "BANK_ACCOUNT":
                    masked_val = _mask_bank_card(original)
                elif pii_type == "EMAIL_ADDRESS":
                    masked_val = _mask_email(original)
                else:
                    masked_val = rule["replacement"]
                raw_matches.append(PIIMatch(
                    type=pii_type, start=m.start(), end=m.end(),
                    original=original, masked=masked_val,
                ))

        raw_matches.sort(key=lambda x: x.start, reverse=True)
        result = text
        for m in raw_matches:
            result = result[:m.start] + m.masked + result[m.end:]

        if raw_matches:
            logger.info(
                "PII detected: %d matches across types=%s",
                len(raw_matches),
                {m.type for m in raw_matches},
            )
        return PIIResult(masked_text=result, matches=list(reversed(raw_matches)))

    def _mask_with_presidio(self, text: str) -> PIIResult:
        assert self._presidio is not None
        presidio_results = self._presidio.analyze(text=text, language="zh")
        matches: list[PIIMatch] = []
        result = text
        for r in sorted(presidio_results, key=lambda x: x.start, reverse=True):
            pii_type = r.entity_type
            original = text[r.start : r.end]
            if pii_type in self._rules:
                replacement = self._rules[pii_type]["replacement"]
                if pii_type == "BANK_ACCOUNT":
                    replacement = _mask_bank_card(original)
                elif pii_type == "EMAIL_ADDRESS":
                    replacement = _mask_email(original)
            else:
                replacement = "[***]"

            matches.append(PIIMatch(
                type=pii_type,
                start=r.start,
                end=r.end,
                original=original,
                masked=replacement,
            ))
            result = result[: r.start] + replacement + result[r.end :]

        return PIIResult(masked_text=result, matches=matches)

    @classmethod
    def from_config(cls, config_path: str | None = None) -> PIIDetector:
        if config_path is None:
            from pathlib import Path
            config_path = str(Path(__file__).parent.parent / "config" / "safety_rules.yaml")
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            pii_config = data.get("pii", {})
            enabled_types = pii_config.get("enabled_types", list(cls.TYPES.keys()))
            return cls(enabled_types=enabled_types)
        except Exception:
            return cls()


def _mask_bank_card(number: str) -> str:
    cleaned = re.sub(r"\D", "", number)
    if len(cleaned) >= 8:
        return cleaned[:4] + "****" + cleaned[-4:]
    return "****"


def _mask_email(email: str) -> str:
    parts = email.split("@", 1)
    if len(parts) == 2:
        return parts[0][:2] + "***@" + parts[1]
    return "***@***"
