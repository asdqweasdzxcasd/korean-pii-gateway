"""
title: Korean PII Filter
author: korean-pii-gateway
description: 한국어 개인정보(주민등록번호·전화번호·계좌번호 등)를 모델로 보내기 전에 마스킹합니다.
requirements: korean-pii
version: 0.1.0
license: MIT
"""
from pydantic import BaseModel

from korean_pii import MaskPolicy, mask


class Filter:
    class Valves(BaseModel):
        # format: 형식 보존 마스킹, placeholder: [주민등록번호] 라벨 치환
        mask_mode: str = "format"

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        policy = MaskPolicy(mode=self.valves.mask_mode)
        for message in body.get("messages", []):
            content = message.get("content")
            if isinstance(content, str):
                message["content"] = mask(content, policy).text
        return body
