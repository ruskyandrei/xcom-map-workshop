"""Where an Enemy Within install keeps the game's files (Long War Rebalance or plain): its maps in
XEW/XComGame/CookedPCConsole and its config in XEW/XComGame/Config. The Build (build.py) reads the base map, the
intros, the streams and the config lines there, and the prefab test's stage (prefab_stage.py) the blank map."""
from pathlib import Path


def lwr_file(lwr, *parts):
    return Path(lwr).joinpath('XEW', 'XComGame', *parts)
