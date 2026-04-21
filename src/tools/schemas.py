"""
Tool Schemas — Pydantic validation cho tat ca device commands
==============================================================
Moi lenh tu LLM PHAI duoc validate qua schema truoc khi thuc thi.

5 loai thiet bi:
- Light    (den)
- Switch   (cong tac / bep)
- Lock     (khoa cua)
- Climate  (dieu hoa)
- Sensor   (cam bien — chi doc)

Nguyen tac:
- entity_id PHAI match regex nghiem nhat
- action chi nhan Literal values — khong cho tu do
- params co range constraints (brightness 0-255, temp 16-30)
- LockCommand KHONG co unlock — chan tuyet doi
"""

from __future__ import annotations

from typing import Literal, Union
from pydantic import BaseModel, Field


# ── Light ──────────────────────────────────────────────────

class LightCommand(BaseModel):
    """Lenh dieu khien den."""
    entity_id: str = Field(
        ...,
        pattern=r"^light\.[a-z0-9_]+$",
        description="ID den trong Home Assistant",
        examples=["light.phong_ngu", "light.phong_khach"],
    )
    action: Literal["turn_on", "turn_off", "set_brightness", "set_color"] = Field(
        ..., description="Hanh dong"
    )
    brightness: int | None = Field(
        None, ge=0, le=255,
        description="Do sang (0=tat, 255=max)",
    )
    color_temp: int | None = Field(
        None, ge=153, le=500,
        description="Nhiet do mau (Mireds)",
    )


# ── Switch ─────────────────────────────────────────────────

class SwitchCommand(BaseModel):
    """Lenh dieu khien cong tac (bep, quat, o cam)."""
    entity_id: str = Field(
        ...,
        pattern=r"^switch\.[a-z0-9_]+$",
        description="ID switch trong Home Assistant",
        examples=["switch.kitchen_stove", "switch.fan_living"],
    )
    action: Literal["turn_on", "turn_off"] = Field(
        ..., description="Hanh dong"
    )
    # Khong co param tu do — LLM khong the inject gi them


# ── Lock ───────────────────────────────────────────────────

class LockCommand(BaseModel):
    """
    Lenh dieu khien khoa cua.
    CHI CO LOCK — KHONG CO UNLOCK qua AI.
    """
    entity_id: str = Field(
        ...,
        pattern=r"^lock\.[a-z0-9_]+$",
        description="ID khoa trong Home Assistant",
        examples=["lock.cua_chinh"],
    )
    action: Literal["lock"] = Field(
        ..., description="Chi cho phep KHOA"
    )
    # unlock bi chan tuyet doi tai Rule Engine


# ── Climate ────────────────────────────────────────────────

class ClimateCommand(BaseModel):
    """Lenh dieu khien dieu hoa."""
    entity_id: str = Field(
        ...,
        pattern=r"^climate\.[a-z0-9_]+$",
        description="ID dieu hoa trong Home Assistant",
        examples=["climate.phong_ngu"],
    )
    action: Literal["set_temperature", "set_hvac_mode", "turn_off"] = Field(
        ..., description="Hanh dong"
    )
    temperature: float | None = Field(
        None, ge=16.0, le=30.0,
        description="Nhiet do muc tieu (16-30 do C)",
    )
    hvac_mode: Literal["cool", "heat", "fan_only", "auto", "off"] | None = Field(
        None, description="Che do hoat dong",
    )


# ── Sensor ─────────────────────────────────────────────────

class SensorCommand(BaseModel):
    """Lenh doc cam bien (CHI DOC — khong dieu khien)."""
    entity_id: str = Field(
        ...,
        pattern=r"^(sensor|binary_sensor)\.[a-z0-9_]+$",
        description="ID cam bien",
        examples=["sensor.nhiet_do_phong", "binary_sensor.cua_ra_vao"],
    )
    action: Literal["get_state"] = Field(
        ..., description="Chi cho phep doc trang thai"
    )


# ── Union Type ─────────────────────────────────────────────

HomeCommand = Union[
    LightCommand,
    SwitchCommand,
    LockCommand,
    ClimateCommand,
    SensorCommand,
]

# ── Schema Registry (de gateway lookup) ────────────────────

SCHEMA_MAP: dict[str, type[BaseModel]] = {
    "light": LightCommand,
    "switch": SwitchCommand,
    "lock": LockCommand,
    "climate": ClimateCommand,
    "sensor": SensorCommand,
    "binary_sensor": SensorCommand,
}


def get_schema_for_entity(entity_id: str) -> type[BaseModel] | None:
    """
    Tra ve Pydantic schema phu hop voi entity_id.

    Args:
        entity_id: "light.phong_ngu" → tra ve LightCommand

    Returns:
        Schema class hoac None neu khong tim thay.
    """
    entity_type = entity_id.split(".")[0] if "." in entity_id else ""
    return SCHEMA_MAP.get(entity_type)
