"""Where an Enemy Within install (Long War Rebalance or plain) keeps the game's files: its maps in
XEW/XComGame/CookedPCConsole and its config in XEW/XComGame/Config, the layout settings.py spells (ew_folder,
game_cooked, game_config). The Build (build.py) reads the base map, the intros, the streams and the config lines
there, and the prefab test's stage (prefab_stage.py) the blank map."""
import settings


def lwr_file(lwr, *parts):
    return settings.ew_folder(lwr).joinpath(*parts)
