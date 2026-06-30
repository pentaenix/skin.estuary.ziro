from __future__ import annotations

import xbmc
import xbmcgui
import xbmcvfs

from ..db import GameDatabase
from ..paths import artwork_dir
from .enricher import _artwork_path, _save_image
from .providers import PROVIDER_SCREENSCRAPER, game_artwork_provider
from .screenscraper import list_media_urls, lookup_game

ART_TYPES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "cover": ("Cover / box art", "cover_path", ("box-2d", "boitiers_2d", "box2d")),
    "fanart": ("Fanart", "fanart_path", ("fanart",)),
    "logo": ("Logo / wheel", "logo_path", ("wheel", "wheel-hd", "marquee")),
    "screenshot": ("Screenshot", "screenshot_path", ("ss", "screenshot")),
}


def _preview_image(path: str) -> None:
    if not path or not xbmcvfs.exists(path):
        return
    window = xbmcgui.Window(10000)
    window.setProperty("infobackground", path)
    xbmc.executebuiltin("ActivateWindow(1104)")


def choose_game_art(game_id: int) -> bool:
    db = GameDatabase()
    game = db.get_game(game_id)
    if not game:
        xbmcgui.Dialog().notification("Ziro Games", "Game not found", xbmcgui.NOTIFICATION_ERROR, 3000)
        return False

    type_labels = [label for label, _, _ in ART_TYPES.values()]
    type_keys = list(ART_TYPES.keys())
    picked_type = xbmcgui.Dialog().select("Choose artwork type", type_labels)
    if picked_type < 0:
        return False

    art_key = type_keys[picked_type]
    label, field_name, needles = ART_TYPES[art_key]

    options: list[tuple[str, str]] = []
    current_path = game.get(field_name) or ""
    if current_path and xbmcvfs.exists(current_path):
        options.append((f"Current {label.lower()}", current_path))

    if game_artwork_provider() == PROVIDER_SCREENSCRAPER:
        try:
            jeu = lookup_game(
                platform_id=game["platform_id"],
                title=game["title"],
                rom_path=game.get("rom_path") or "",
                ss_game_id=int(game["ss_game_id"]) if game.get("ss_game_id") else None,
            )
            if jeu:
                options.extend(list_media_urls(jeu, *needles))
        except Exception as exc:
            xbmc.log(f"[Ziro Games] art picker lookup failed: {exc}", xbmc.LOGWARNING)

    art_dir = artwork_dir() / str(game_id)
    if art_dir.exists():
        for path in sorted(art_dir.iterdir()):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            local = str(path)
            if any(local == existing for _, existing in options):
                continue
            options.append((f"Saved · {path.name}", local))

    if not options:
        xbmcgui.Dialog().ok(
            "Ziro Games",
            f"No alternate {label.lower()} images are available yet.\n\nTry Refresh metadata first.",
        )
        return False

    labels = [entry[0] for entry in options]
    picked = xbmcgui.Dialog().select(f"Choose {label.lower()}", labels)
    if picked < 0:
        return False

    selected_label, selected_value = options[picked]
    if selected_value.startswith("http"):
        saved_path = _save_image(selected_value, _artwork_path(game_id, art_key, selected_value))
    else:
        saved_path = selected_value

    db.update_game_artwork(game_id, {field_name: saved_path})
    db.execute("UPDATE games SET manual_metadata_locked=1 WHERE id=?", (game_id,))
    if xbmcgui.Dialog().yesno("Ziro Games", f"Preview “{selected_label}” before keeping it?"):
        _preview_image(saved_path)
    xbmcgui.Dialog().notification("Ziro Games", f"{label} updated", xbmcgui.NOTIFICATION_INFO, 2500)
    return True
