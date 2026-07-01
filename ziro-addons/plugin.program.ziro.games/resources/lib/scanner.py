from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcvfs

from .db import GameDatabase
from .paths_filter import is_library_rom_path, is_placeholder_rom_path, is_valid_game_title, rom_file_exists
from .platforms import extensions_for, get_platform, iter_profile_defs, source_dict
from .metadata.providers import PROVIDER_SKRAPER, game_artwork_provider
from .metadata.local_metadata import clear_gamelist_cache, import_metadata_for_game

ADDON = xbmcaddon.Addon("plugin.program.ziro.games")

TITLE_JUNK = re.compile(r"\s*[\(\[].*?[\)\]]\s*")
SEPARATORS = re.compile(r"[._]+")
SKIP_DIR_NAMES = {".", "..", "@eaDir", "#recycle", "System Volume Information", "$recycle.bin"}
REMOTE_SCHEMES = ("smb://", "nfs://", "ftp://", "http://", "https://", "dav://", "upnp://")


@dataclass
class SourceScanResult:
    platform_id: str
    platform_name: str
    folder_path: str
    imported: int = 0
    files_seen: int = 0
    matched: int = 0
    skipped_samples: list[str] = field(default_factory=list)
    status: str = "ok"
    message: str = ""
    listing_method: str = ""


@dataclass
class ScanResult:
    imported: int = 0
    sources: list[SourceScanResult] = field(default_factory=list)

    def summary(self) -> str:
        if self.imported:
            return f"Scan complete: {self.imported} games imported."
        if not self.sources:
            return "Scan complete: 0 games. No enabled sources were found.\nAdd a source under Games -> Sources first."
        lines = ["Scan complete: 0 games imported."]
        for source in self.sources:
            lines.append(source.message or f"{source.platform_name}: {source.status}")
        return "\n".join(lines)


def normalize_folder(path: str) -> str:
    path = (path or "").strip().strip('"')
    if not path:
        return ""
    return path.rstrip("/\\")


def is_remote_path(path: str) -> bool:
    lower = path.lower()
    return lower.startswith(REMOTE_SCHEMES)


def path_accessible(path: str) -> bool:
    path = normalize_folder(path)
    if not path:
        return False
    if xbmcvfs.exists(path):
        return True
    return not is_remote_path(path) and os.path.isdir(path)


def resolve_folder_path(path: str) -> str:
    """Return the first path Kodi VFS or the OS can see as a folder."""
    path = normalize_folder(path)
    if not path:
        return ""
    candidates: list[str] = []
    for candidate in (path, normalize_folder(xbmcvfs.translatePath(path))):
        if candidate and candidate not in candidates:
            candidates.append(candidate)
    for candidate in candidates:
        if path_accessible(candidate):
            return candidate
    return path


def display_name(path: str) -> str:
    trimmed = path.rstrip("/\\")
    return trimmed.replace("\\", "/").split("/")[-1] or trimmed


def clean_title(path: str | Path) -> str:
    name = display_name(str(path))
    if "." in name:
        name = ".".join(name.split(".")[:-1]) or name
    title = SEPARATORS.sub(" ", name)
    title = TITLE_JUNK.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title or name


def sort_title(title: str) -> str:
    return re.sub(r"^(the|a|an)\s+", "", title.lower()).strip()


def join_path(folder: str, child: str, use_os: bool) -> str:
    if use_os and not is_remote_path(folder):
        return os.path.join(folder, child)
    if folder.endswith(("/", "\\")):
        return folder + child
    if "\\" in folder and "/" not in folder.replace("://", ""):
        return folder + "\\" + child
    return folder + "/" + child


def normalize_extensions(extensions: list[str]) -> set[str]:
    allowed: set[str] = set()
    for ext in extensions:
        token = ext.strip().lower()
        if not token:
            continue
        if not token.startswith("."):
            token = f".{token}"
        allowed.add(token)
    return allowed


def file_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def list_directory(folder: str) -> tuple[list[str], list[str], str] | None:
    """List a folder via Kodi VFS, falling back to the OS for local paths."""
    if xbmcvfs.exists(folder):
        try:
            dirs, files = xbmcvfs.listdir(folder)
            return list(dirs), list(files), "xbmcvfs"
        except Exception as exc:
            xbmc.log(f"[Ziro Games Scanner] xbmcvfs.listdir failed for {folder}: {exc}", xbmc.LOGWARNING)

    if not is_remote_path(folder) and os.path.isdir(folder):
        try:
            dirs: list[str] = []
            files: list[str] = []
            for entry in os.listdir(folder):
                full = os.path.join(folder, entry)
                if os.path.isdir(full):
                    dirs.append(entry)
                elif os.path.isfile(full):
                    files.append(entry)
            return dirs, files, "os"
        except OSError as exc:
            xbmc.log(f"[Ziro Games Scanner] os.listdir failed for {folder}: {exc}", xbmc.LOGWARNING)
            return None

    return None


def iter_games(folder: str, extensions: list[str], recursive: bool = True, stats: SourceScanResult | None = None):
    folder = resolve_folder_path(folder)
    allowed = normalize_extensions(extensions)
    if not folder:
        return
    if not path_accessible(folder):
        if stats:
            stats.status = "missing"
            stats.message = f"{stats.platform_name}: folder not found ({folder})"
        return

    listing = list_directory(folder)
    if listing is None:
        if stats:
            stats.status = "list_error"
            stats.message = f"{stats.platform_name}: could not read folder ({folder})"
        return

    dirs, files, listing_method = listing
    if stats and not stats.listing_method:
        stats.listing_method = listing_method
    use_os = listing_method == "os"

    for filename in files:
        if stats:
            stats.files_seen += 1
        suffix = file_extension(filename)
        if suffix in allowed:
            if stats:
                stats.matched += 1
            yield join_path(folder, filename, use_os)
        elif stats and len(stats.skipped_samples) < 20:
            stats.skipped_samples.append(f"{filename} ({suffix or 'no extension'})")

    if recursive:
        for dirname in dirs:
            if dirname in SKIP_DIR_NAMES or dirname.startswith("."):
                continue
            child = join_path(folder, dirname, use_os)
            yield from iter_games(child, extensions, True, stats)


def configure_defaults(db: GameDatabase) -> None:
    """Ensure emulator profiles exist from addon settings."""
    for profile in iter_profile_defs():
        exe = ADDON.getSetting(profile["emulator_setting"])
        db.ensure_emulator_profile({
            "id": profile["id"],
            "name": profile["name"],
            "platform_id": profile["platform_id"],
            "executable_path": exe,
            "arguments_template": profile["arguments_template"],
            "working_directory": str(Path(exe).parent) if exe else "",
            "process_name": profile["process_name"],
            "exit_hotkey": "",
            "fullscreen": True,
            "return_focus_to_kodi": True,
        })


def source_for_platform(platform_id: str, folder_path: str) -> dict:
    folder = resolve_folder_path(folder_path) or normalize_folder(folder_path)
    payload = source_dict(platform_id, folder, label=display_name(folder))
    return payload


def effective_extensions(platform_id: str, stored: str | None) -> list[str]:
    catalog = [f".{ext}" for ext in extensions_for(platform_id)]
    stored_exts = [
        f".{ext.strip().lstrip('.')}"
        for ext in (stored or "").split(",")
        if ext.strip()
    ]
    merged = normalize_extensions(stored_exts or catalog)
    merged.update(normalize_extensions(catalog))
    return sorted(merged)


def finalize_source_result(result: SourceScanResult, extensions: list[str]) -> None:
    if result.imported:
        result.status = "ok"
        result.message = f"{result.platform_name}: imported {result.imported} games."
        return
    if result.status not in {"ok", ""}:
        if not result.message:
            result.message = f"{result.platform_name}: {result.status.replace('_', ' ')}."
        return
    if result.files_seen == 0:
        result.status = "empty_folder"
        method = f" via {result.listing_method}" if result.listing_method else ""
        result.message = (
            f"{result.platform_name}: folder is empty or unreadable{method}.\n"
            f"Path: {result.folder_path}\n"
            "Check that this is the folder that directly contains your .gba files, "
            "or a parent folder with subfolders inside it."
        )
        return
    if result.matched == 0:
        allowed = ", ".join(extensions)
        sample = "\n".join(f"  - {line}" for line in result.skipped_samples[:8])
        result.status = "no_extension_match"
        result.message = (
            f"{result.platform_name}: found {result.files_seen} files but none matched {allowed}.\n"
            f"Path: {result.folder_path}"
        )
        if sample:
            result.message += f"\nExamples:\n{sample}"
        return
    result.status = "no_import"
    result.message = f"{result.platform_name}: files matched but none were imported."


def purge_junk_games(db: GameDatabase) -> int:
    rows = db.rows("SELECT id, rom_path, title FROM games WHERE hidden=0")
    hidden = 0
    for row in rows:
        rom_path = row.get("rom_path", "")
        title = (row.get("title") or "").strip()
        if (
            not is_library_rom_path(rom_path)
            or is_placeholder_rom_path(rom_path)
            or not rom_file_exists(rom_path)
            or not title
            or not is_valid_game_title(title)
        ):
            db.execute(
                "UPDATE games SET hidden=1, last_played=NULL, play_count=0 WHERE id=?",
                (row["id"],),
            )
            hidden += 1
    if hidden:
        xbmc.log(f"[Ziro Games Scanner] hid {hidden} junk library entries", xbmc.LOGINFO)
    return hidden


def scan(db: GameDatabase) -> ScanResult:
    configure_defaults(db)
    clear_gamelist_cache()
    purge_junk_games(db)
    outcome = ScanResult()
    sources = db.list_sources(enabled_only=True)
    if not sources:
        db.clear_play_state_for_hidden_games()
        xbmc.log("[Ziro Games Scanner] no enabled sources configured", xbmc.LOGINFO)
        try:
            from .home_state import refresh_home_platform_properties

            refresh_home_platform_properties(db)
        except Exception as exc:
            xbmc.log(f"[Ziro Games Scanner] home refresh failed: {exc}", xbmc.LOGWARNING)
        return outcome

    for source in sources:
        platform_id = source["platform_id"]
        platform = get_platform(platform_id)
        result = SourceScanResult(
            platform_id=platform_id,
            platform_name=(platform.name if platform else platform_id),
            folder_path=normalize_folder(source["folder_path"]),
        )
        outcome.sources.append(result)

        if not platform:
            result.status = "unsupported_platform"
            result.message = f"Unsupported platform: {platform_id}"
            xbmc.log(f"[Ziro Games Scanner] unsupported source platform: {platform_id}", xbmc.LOGWARNING)
            continue

        folder = resolve_folder_path(source["folder_path"])
        result.folder_path = folder
        extensions = effective_extensions(platform_id, source.get("file_extensions"))
        xbmc.log(
            f"[Ziro Games Scanner] scanning {platform_id} folder={folder} extensions={extensions}",
            xbmc.LOGINFO,
        )

        if not folder or not path_accessible(folder):
            result.status = "missing"
            result.message = (
                f"{platform.name}: folder not found.\n"
                f"Stored path: {source['folder_path']}"
            )
            xbmc.log(
                f"[Ziro Games Scanner] source missing for {platform_id}: {source['folder_path']}",
                xbmc.LOGWARNING,
            )
            continue

        db.execute(
            "UPDATE sources SET file_extensions=? WHERE id=?",
            (",".join(ext.lstrip(".") for ext in extensions), source["id"]),
        )

        for rom in iter_games(folder, extensions, bool(source.get("recursive", 1)), result):
            rom_path = str(rom)
            if not is_library_rom_path(rom_path):
                continue
            title = clean_title(rom)
            db.upsert_game({
                "title": title,
                "sort_title": sort_title(title),
                "platform_id": platform_id,
                "rom_path": rom_path,
                "emulator_profile_id": source.get("emulator_profile_id") or platform.profile_id,
                "source_id": source.get("id"),
                "description": f"Imported from {folder}",
            })
            if game_artwork_provider() == PROVIDER_SKRAPER:
                row = db.one("SELECT id FROM games WHERE rom_path=?", (rom_path,))
                if row:
                    import_metadata_for_game(
                        db,
                        int(row["id"]),
                        source_folder=folder,
                        platform_id=platform_id,
                    )
            result.imported += 1

        finalize_source_result(result, extensions)
        outcome.imported += result.imported
        xbmc.log(
            f"[Ziro Games Scanner] {platform_id} listing={result.listing_method or 'none'} "
            f"files_seen={result.files_seen} matched={result.matched} imported={result.imported} "
            f"status={result.status}",
            xbmc.LOGINFO,
        )

    try:
        from .home_state import refresh_home_platform_properties

        refresh_home_platform_properties(db)
    except Exception as exc:
        xbmc.log(f"[Ziro Games Scanner] home refresh failed: {exc}", xbmc.LOGWARNING)

    return outcome
