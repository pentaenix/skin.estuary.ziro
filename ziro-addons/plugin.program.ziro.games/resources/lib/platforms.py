from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PlatformDef:
    id: str
    name: str
    short_name: str
    manufacturer: str
    sort_order: int
    extensions: tuple[str, ...]
    profile_id: str
    emulator_setting: str
    emulator_name: str
    arguments_template: str
    process_name: str
    retroarch_core: str = ""


PLATFORMS: dict[str, PlatformDef] = {}


def _add(platform: PlatformDef) -> None:
    PLATFORMS[platform.id] = platform


def resolve_core_path(executable: str, core_name: str) -> str:
    if not executable or not core_name:
        return ""
    exe = Path(executable)
    candidates = [
        exe.parent / "cores" / core_name,
        exe.parent.parent / "cores" / core_name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


# Nintendo
_add(PlatformDef("nes", "Nintendo Entertainment System", "NES", "Nintendo", 10, (".nes", ".zip", ".7z"), "retroarch_nes", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "nestopia_libretro.dll"))
_add(PlatformDef("snes", "Super Nintendo", "SNES", "Nintendo", 20, (".sfc", ".smc", ".zip", ".7z"), "retroarch_snes", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "snes9x_libretro.dll"))
_add(PlatformDef("n64", "Nintendo 64", "N64", "Nintendo", 30, (".n64", ".z64", ".v64", ".zip", ".7z"), "retroarch_n64", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "mupen64plus_next_libretro.dll"))
_add(PlatformDef("gb", "Game Boy", "GB", "Nintendo", 40, (".gb", ".zip"), "retroarch_gb", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "gambatte_libretro.dll"))
_add(PlatformDef("gbc", "Game Boy Color", "GBC", "Nintendo", 50, (".gbc", ".zip"), "retroarch_gbc", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "gambatte_libretro.dll"))
_add(PlatformDef("gba", "Game Boy Advance", "GBA", "Nintendo", 60, (".gba", ".zip"), "mgba_gba", "emulator_mgba", "mGBA", '-f "{rom_path}"', "mGBA.exe"))
_add(PlatformDef("nds", "Nintendo DS", "NDS", "Nintendo", 70, (".nds", ".zip"), "retroarch_nds", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "melonds_libretro.dll"))
_add(PlatformDef("3ds", "Nintendo 3DS", "3DS", "Nintendo", 80, (".3ds", ".cia", ".cxi", ".zip"), "citra_3ds", "emulator_citra", "Citra", '"{rom_path}"', "citra-qt.exe"))
_add(PlatformDef("gamecube", "Nintendo GameCube", "GameCube", "Nintendo", 90, (".rvz", ".iso", ".gcm", ".gcz"), "dolphin_gamecube", "emulator_dolphin", "Dolphin", '-b -e "{rom_path}"', "Dolphin.exe"))
_add(PlatformDef("wii", "Nintendo Wii", "Wii", "Nintendo", 100, (".rvz", ".iso", ".wbfs", ".wad"), "dolphin_wii", "emulator_dolphin", "Dolphin", '-b -e "{rom_path}"', "Dolphin.exe"))
_add(PlatformDef("wiiu", "Nintendo Wii U", "Wii U", "Nintendo", 110, (".wud", ".wux", ".rpx", ".wua"), "cemu_wiiu", "emulator_cemu", "Cemu", '-g "{rom_path}"', "Cemu.exe"))
_add(PlatformDef("switch", "Nintendo Switch", "Switch", "Nintendo", 120, (".nsp", ".xci", ".nca"), "yuzu_switch", "emulator_yuzu", "yuzu", '-g "{rom_path}"', "yuzu.exe"))

# Sega
_add(PlatformDef("sms", "Sega Master System", "SMS", "Sega", 200, (".sms", ".zip"), "retroarch_sms", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "genesis_plus_gx_libretro.dll"))
_add(PlatformDef("genesis", "Sega Genesis / Mega Drive", "Genesis", "Sega", 210, (".md", ".gen", ".smd", ".zip", ".7z"), "retroarch_genesis", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "genesis_plus_gx_libretro.dll"))
_add(PlatformDef("segacd", "Sega CD", "Sega CD", "Sega", 220, (".cue", ".bin", ".chd", ".iso"), "retroarch_segacd", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "genesis_plus_gx_libretro.dll"))
_add(PlatformDef("saturn", "Sega Saturn", "Saturn", "Sega", 230, (".cue", ".bin", ".chd", ".iso"), "retroarch_saturn", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "yabause_libretro.dll"))
_add(PlatformDef("dreamcast", "Sega Dreamcast", "Dreamcast", "Sega", 240, (".gdi", ".cdi", ".chd", ".cue"), "retroarch_dreamcast", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "flycast_libretro.dll"))

# Sony
_add(PlatformDef("ps1", "PlayStation", "PS1", "Sony", 300, (".bin", ".cue", ".pbp", ".chd", ".iso"), "retroarch_ps1", "emulator_retroarch", "RetroArch", '-L "{core_path}" "{rom_path}"', "retroarch.exe", "pcsx_rearmed_libretro.dll"))
_add(PlatformDef("ps2", "PlayStation 2", "PS2", "Sony", 310, (".iso", ".chd", ".cso"), "pcsx2_ps2", "emulator_pcsx2", "PCSX2", '-batch -nogui "{rom_path}"', "pcsx2-qt.exe"))
_add(PlatformDef("ps3", "PlayStation 3", "PS3", "Sony", 320, (".iso", ".ps3"), "rpcs3_ps3", "emulator_rpcs3", "RPCS3", '"{rom_path}"', "rpcs3.exe"))
_add(PlatformDef("psp", "PlayStation Portable", "PSP", "Sony", 330, (".iso", ".cso", ".pbp"), "ppsspp_psp", "emulator_ppsspp", "PPSSPP", '"{rom_path}"', "PPSSPPWindows64.exe"))
_add(PlatformDef("psvita", "PlayStation Vita", "PS Vita", "Sony", 340, (".vpk", ".mai", ".zip"), "vita3k_psvita", "emulator_vita3k", "Vita3K", '"{rom_path}"', "Vita3K.exe"))
_add(PlatformDef("ps4", "PlayStation 4", "PS4", "Sony", 350, (".pkg", ".fpkg"), "ps4_placeholder", "emulator_ps4", "PS4 emulator", '"{rom_path}"', "shadPS4.exe"))

# Microsoft
_add(PlatformDef("xbox", "Xbox", "Xbox", "Microsoft", 400, (".iso", ".xbe"), "xemu_xbox", "emulator_xemu", "xemu", '"{rom_path}"', "xemu.exe"))
_add(PlatformDef("xbox360", "Xbox 360", "Xbox 360", "Microsoft", 410, (".iso", ".xex", ".xbe"), "xenia_xbox360", "emulator_xenia", "Xenia", '"{rom_path}"', "xenia.exe"))
_add(PlatformDef("xboxone", "Xbox One", "Xbox One", "Microsoft", 420, (".iso", ".xvc"), "xenia_xboxone", "emulator_xenia", "Xenia", '"{rom_path}"', "xenia.exe"))
_add(PlatformDef("xboxseries", "Xbox Series X|S", "Xbox Series", "Microsoft", 430, (".iso", ".xvc"), "xenia_xboxseries", "emulator_xenia", "Xenia", '"{rom_path}"', "xenia.exe"))

LEGACY_SOURCE_SETTINGS: dict[str, str] = {
    "source_gamecube": "gamecube",
    "source_wii": "wii",
    "source_gba": "gba",
}


def get_platform(platform_id: str) -> PlatformDef | None:
    return PLATFORMS.get(platform_id)


def platform_ids() -> frozenset[str]:
    return frozenset(PLATFORMS)


def platform_choices() -> list[dict[str, str]]:
    ordered = sorted(PLATFORMS.values(), key=lambda p: (p.sort_order, p.name))
    return [{"id": p.id, "label": f"{p.manufacturer} — {p.name}"} for p in ordered]


def all_platform_rows() -> list[tuple[str, str, str, str, int]]:
    return [(p.id, p.name, p.short_name, p.manufacturer, p.sort_order) for p in sorted(PLATFORMS.values(), key=lambda p: p.sort_order)]


def extensions_for(platform_id: str) -> list[str]:
    platform = get_platform(platform_id)
    if not platform:
        return []
    return [ext.lstrip(".") for ext in platform.extensions]


def source_dict(platform_id: str, folder_path: str, label: str | None = None) -> dict:
    platform = get_platform(platform_id)
    if not platform:
        raise ValueError(f"Unknown platform: {platform_id}")
    return {
        "platform_id": platform_id,
        "folder_path": folder_path,
        "recursive": True,
        "file_extensions": extensions_for(platform_id),
        "emulator_profile_id": platform.profile_id,
        "label": label,
    }


def iter_profile_defs() -> Iterable[dict]:
    seen: set[str] = set()
    for platform in sorted(PLATFORMS.values(), key=lambda p: p.sort_order):
        if platform.profile_id in seen:
            continue
        seen.add(platform.profile_id)
        yield {
            "id": platform.profile_id,
            "name": f"{platform.emulator_name} ({platform.short_name})",
            "platform_id": platform.id,
            "emulator_setting": platform.emulator_setting,
            "arguments_template": platform.arguments_template,
            "process_name": platform.process_name,
            "retroarch_core": platform.retroarch_core,
        }
