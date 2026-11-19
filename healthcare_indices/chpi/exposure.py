"""Frozen, pre-bind CHPI insurance exposure schedule (research only).

Rate data comes from Tynbil/Oriel. This separate schedule is supplied by the
insured/underwriter and MUST NOT affect the independent index fixing.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
import hashlib
import json
from .hybrid import ValidationError, positive_money

@dataclass(frozen=True)
class ExposureLine:
    line_id: str
    region: str
    service_category: str
    network: str
    exposure_usd: str
    reference_index: str

    def validate(self):
        if not all((self.line_id,self.region,self.service_category,self.network,self.reference_index)):
            raise ValidationError("Exposure line identifiers must be populated")
        positive_money(self.exposure_usd, "Exposure line amount")

@dataclass(frozen=True)
class ExposureSchedule:
    insured_id: str
    policy_id: str
    direction: str
    period_start: str
    period_end: str
    frozen_at: str
    lines: tuple[ExposureLine, ...]
    schedule_version: str = "EXPOSURE-RESEARCH-0.1"
    evidence_reference: str = "SYNTHETIC"

    def validate(self):
        if not self.insured_id or not self.policy_id or not self.evidence_reference:
            raise ValidationError("Missing insured, policy or evidence identifier")
        if self.direction != "payer_cost_increase":
            raise ValidationError("Only payer-side reimbursement price risk currently supported")
        try:
            start,end,freeze=(date.fromisoformat(s) for s in (
                self.period_start,self.period_end,self.frozen_at))
        except ValueError as exc:
            raise ValidationError("Schedule requires ISO dates") from exc
        if not freeze < start < end:
            raise ValidationError("Exposure schedule must freeze before coverage start")
        if not self.lines:
            raise ValidationError("Exposure schedule has no lines")
        ids=set()
        for line in self.lines:
            line.validate()
            if line.line_id in ids:
                raise ValidationError("Duplicate exposure line identifier")
            ids.add(line.line_id)

    def canonical(self):
        self.validate()
        payload=asdict(self)
        payload["lines"]=sorted(payload["lines"],key=lambda r:r["line_id"])
        return json.dumps(payload,sort_keys=True,separators=(",",":"))

    def digest(self):
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()

    def total_exposure(self):
        self.validate()
        return sum((positive_money(line.exposure_usd,"Exposure line") for line in self.lines),Decimal("0"))

    def reference_weight_map(self):
        total=self.total_exposure()
        result={}
        for line in self.lines:
            result[line.reference_index]=result.get(line.reference_index,Decimal("0"))+positive_money(line.exposure_usd,"Exposure line")
        return {key:float(v/total) for key,v in sorted(result.items())}

def read_schedule(path):
    from pathlib import Path
    raw=json.loads(Path(path).read_text(encoding="utf-8"))
    schedule=ExposureSchedule(**{**raw,"lines":tuple(ExposureLine(**x) for x in raw["lines"])})
    schedule.validate()
    return schedule
