"""Starting the game straight in a battle on a map (Play in game): the console commands, and the process to start.

The game runs a file of console commands as it starts when given -EXEC=<file> (it looks in XEW\\Binaries), and the
console's `open <Map>` loads a map as a battle with no campaign behind it: Firaxis's own developer path, still in the
shipped game (EXP-29, findings register F-72). The battle is an ordinary one on the map (its streams and landing as its
DefaultMaps.ini record has them, aliens of the game's choosing), with a squad the commands set:
- `set XComContentManager bAllowJITLoad True`: the game loads a soldier's body and weapons when they are first needed.
  Nothing else loads them on this path (in a campaign the base does, before the mission), and without it the squad is
  invisible;
- `set XComOnlineProfileSettings m_aSoldiers (...)`: the squad, six squaddies (SQUAD). The game's own for this path is
  two MEC troopers, a heavy and a support, and under Long War the MECs come without bodies or weapons. Items are
  numbers in the game's item list, which Long War renumbers: ITEMS has LWR's, read from its scripts and played, and
  Long War's are taken to be the same. For plain Enemy Within no squad is set: the game's own plays (not tried).
Both commands make the game save its XComContent.ini with them in it: installs.backup_config keeps the file aside
first and restore_config puts it back after the game closes (F-73).

Through Steam the game is started with `steam.exe -applaunch 200510 -EXEC=<file>`, which needs no launch option set:
Steam hands the argument on, and the game's own launcher (where Enemy Within is picked) hands it to XComEW.exe. An install
whose launcher was replaced starts the game at once: a stand-in that starts XComEW.exe keeps the process name
installs.game_running looks for, a copy of XComEW.exe under the launcher's name would not (F-84). Steam
runs the folder its manifest names, so a game folder parked under another name beside it is refused. A game folder
outside a Steam library is started by its XComEW.exe (not tried).
"""
from pathlib import Path
import re
import subprocess
import sys

APP_ID = '200510'       # XCOM: Enemy Unknown, which Enemy Within is launched from

# The item numbers of the squad's gear in each kind of install (settings.game_kind).
LWR_ITEMS = dict(eItem_Pistol=2, eItem_AssaultRifle=3, eItem_Shotgun=4, eItem_LMG=5, eItem_SniperRifle=6, eItem_RocketLauncher=7,
                 eItem_PsiAmp=37, eItem_ArmorKevlar=59, eItem_ArmorCarapace=60, eItem_Medikit=69, eItem_FragGrenade=81,
                 eItem_NeedleGrenade=87)
ITEMS = dict(lwr=LWR_ITEMS, longwar=LWR_ITEMS)

# Looks the game's own developer squad uses (XComOnlineProfileSettings.ExtendedLaunch_BuildSoldiersFromParts), so
# their heads, hair and voices are ones the game has.
MAN_A = 'iHead=31,iGender=1,iRace=2,iHaircut=20,iHairColor=2,iFacialHair=7,iVoice=1'
MAN_B = 'iHead=36,iGender=1,iRace=3,iHaircut=19,iHairColor=10,iFacialHair=-1,iSkinColor=4,iVoice=1'
MAN_C = 'iHead=16,iGender=1,iHaircut=22,iHairColor=9,iFacialHair=4,iSkinColor=3,iVoice=1'
MAN_D = 'iHead=31,iGender=1,iRace=2,iHaircut=20,iHairColor=8,iFacialHair=-1,iVoice=1'
WOMAN_A = 'iHead=43,iGender=2,iHaircut=10,iHairColor=1,iFacialHair=-1,iSkinColor=1,iVoice=12'
WOMAN_B = 'iHead=43,iGender=2,iHaircut=10,iHairColor=6,iFacialHair=-1,iSkinColor=2,iVoice=12'
# (first name, last name, class, armour, sidearm, weapon, small item, look, country). The heavy's pair is the game's
# own: the machine gun in the sidearm's place and the rocket launcher as the weapon.
SQUAD = (
    ('Tom', 'Alpha', 'eSC_Assault', 'eItem_ArmorKevlar', 'eItem_Pistol', 'eItem_Shotgun', 'eItem_FragGrenade', MAN_A, 15),
    ('Raj', 'Bravo', 'eSC_Support', 'eItem_ArmorKevlar', 'eItem_Pistol', 'eItem_AssaultRifle', 'eItem_FragGrenade', MAN_B, 7),
    ('Mia', 'Charlie', 'eSC_HeavyWeapons', 'eItem_ArmorCarapace', 'eItem_LMG', 'eItem_RocketLauncher', 'eItem_FragGrenade', WOMAN_A, 21),
    ('Leo', 'Delta', 'eSC_Sniper', 'eItem_ArmorKevlar', 'eItem_Pistol', 'eItem_SniperRifle', 'eItem_FragGrenade', MAN_C, 9),
    ('Eva', 'Echo', 'eSC_Support', 'eItem_ArmorCarapace', 'eItem_Pistol', 'eItem_AssaultRifle', 'eItem_Medikit', WOMAN_B, 21),
    ('Sam', 'Foxtrot', 'eSC_Assault', 'eItem_ArmorKevlar', 'eItem_Pistol', 'eItem_AssaultRifle', 'eItem_NeedleGrenade', MAN_D, 15),
)
# A soldier as the game writes its own (getall XComOnlineProfileSettings m_aSoldiers, EXP-29 run 3): the character's
# base numbers are the ones the game gave its developer squad's soldiers.
SOLDIER = ('(kChar=(strName="Soldier",iType=2,kInventory=(iArmor={armor},iPistol={pistol},arrLargeItems[0]={weapon},'
           'iNumLargeItems=1,arrSmallItems[0]={item},iNumSmallItems=1,arrCustomItems[0]={amp},iNumCustomItems=1),'
           'aAbilities[0]=7,aAbilities[27]=1,aProperties[0]=5,aProperties[6]=1,aStats[0]=6,aStats[1]=65,aStats[3]=14,'
           'aStats[7]=30,aStats[10]=27,{traversals},eClass={cls},fBioElectricParticleScale=1.000000),'
           'kSoldier=(strFirstName="{first}",strLastName="{last}",iRank=1,iCountry={country},kAppearance=({look},iBody=-1,'
           'iBodyMaterial=-1,iEyeColor=-1,iFlag={country},iArmorSkin=-1,iArmorDeco=-1,iArmorTint=7)),iUnitLoadoutID=-1)')


class LaunchError(Exception):
    pass


# The aliens of a battle on this path: XGBattleDesc.GenerateAliens makes four pods of the profile's m_eAlienType (five
# on a terror site), and none when it is eChar_None, so a prefab test has no aliens (the battle is never won: an
# empty alien squad is no victory, XGBattle_SP.IsVictory). A play sets the game's own default back, in case the
# profile kept a test's. An EXALT type (eChar_ExaltOperative to eChar_ExaltEliteMedic) gives EXALT pods: the leader,
# one of the same and a sniper or heavy (GetSupportAlien's alternative, picked once for the whole battle), as EXALT
# missions have (missions.play_setup's `aliens`; EXP-57 run 4: two operatives and a heavy in each of four pods).
ALIENS, NO_ALIENS = 'eChar_Sectoid', 'eChar_None'


def squad_text(kind):
    """The squad as the value of m_aSoldiers for a kind of install, or None when its item numbers aren't known."""
    items = ITEMS.get(kind)
    if items is None: return None
    traversals = ','.join(f'aTraversals[{k}]=1' for k in range(1, 10))
    return '(' + ','.join(SOLDIER.format(first=first, last=last, cls=cls, armor=items[armor], pistol=items[pistol],
                                         weapon=items[weapon], item=items[item], amp=items['eItem_PsiAmp'], look=look,
                                         country=country, traversals=traversals)
                          for first, last, cls, armor, pistol, weapon, item, look, country in SQUAD) + ')'


def play_text(map_name, kind, aliens=True, spawn_group=None, lines=(), options=()):
    """The commands file's text: the squad's set-up, the aliens (True: ALIENS, False: none, or a character such as
    'eChar_ExaltOperative'), the mission's own commands (`lines`:
    missions.play_setup's `set` lines for the kind of mission played), then the map, with `spawn_group` (Group<N>)
    the squad's landing (?SpawnGroup=; F-96: the native takes the group of that tag) and the mission's `options`
    ([(name, value)]: the content the campaign's travel line asks for with the kind, ?Meld=1 and the like)."""
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,62}', map_name): raise LaunchError(f'{map_name!r} is not a map name')
    if spawn_group is not None and not re.fullmatch(r'Group\d{1,2}', spawn_group):
        raise LaunchError(f'{spawn_group!r} is not a spawn group')
    for line in lines:
        if not re.fullmatch(r'set [A-Za-z][A-Za-z0-9_]{0,62} [A-Za-z][A-Za-z0-9_]{0,62} [A-Za-z0-9_(),=]{1,2000}', line):
            raise LaunchError(f'{line!r} is not a set command')
    for name, value in options:
        if not (re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,31}', name) and re.fullmatch(r'[A-Za-z0-9]{1,32}', value)):
            raise LaunchError(f'{name}={value} is not an option')
    alien = aliens if isinstance(aliens, str) else ALIENS if aliens else NO_ALIENS
    if not re.fullmatch(r'eChar_[A-Za-z_]{1,40}', alien): raise LaunchError(f'{alien!r} is not a character')
    out = ['set XComContentManager bAllowJITLoad True',
           f'set XComOnlineProfileSettingsDataBlob m_eAlienType {alien}']
    squad = squad_text(kind)
    if squad: out.append(f'set XComOnlineProfileSettings m_aSoldiers {squad}')
    out += list(lines)
    url = (f'?SpawnGroup={spawn_group}' if spawn_group else '') + ''.join(f'?{name}={value}' for name, value in options)
    return '\n'.join(out + [f'open {map_name}{url}']) + '\n'


def user_config(game, documents):
    """The XComContent.ini files the game may write during a play: the user's, under Documents, and one in the game
    folder (the game keeps its settings there when started with -nohomedir)."""
    return [Path(documents) / 'My Games' / 'XCOM - Enemy Within' / 'XComGame' / 'Config' / 'XComContent.ini',
            Path(game) / 'XEW' / 'XComGame' / 'Config' / 'XComContent.ini']


# A play with saving on (F-89, EXP-56): the game starts at its main menu, whose login readies saving, and this key
# there opens the battle. F8 and F9 are Long War's camera keys (F9 the lab's screenshot), F12 Steam's screenshot; F5
# is only the strategy globe's debug look-at, nothing on the main menu.
SAVE_KEY = 'F5'


def start_text(play_file, key=SAVE_KEY):
    """The start file's text for a play with saving on: `key` bound to exec the play's commands file (Input.SetBind
    binds it at once and saves it to XComInput.ini, which saving_config keeps aside), and no open line."""
    if not re.fullmatch(r'F([1-9]|1[0-2])', key): raise LaunchError(f'{key!r} is not a function key')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', play_file): raise LaunchError(f'{play_file!r} is not a file name')
    return f'setbind {key} exec {play_file}\n'


def saving_config(game, documents):
    """The files a play with saving on lets the game write besides user_config's: XComInput.ini (the key's binding)
    and profile.bin (the logged-in game writes its profile, the play's squad in it: EXP-56 run 1 rewrote the lab
    copy's), each in Documents and in the game folder."""
    home = Path(documents) / 'My Games' / 'XCOM - Enemy Within' / 'XComGame'
    own = Path(game) / 'XEW' / 'XComGame'
    return [home / 'Config' / 'XComInput.ini', own / 'Config' / 'XComInput.ini',
            home / 'SaveData' / 'profile.bin', own / 'SaveData' / 'profile.bin']


def steam_exe():
    """Steam's program, from the registry, or None."""
    if sys.platform != 'win32': return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
            path = Path(winreg.QueryValueEx(key, 'SteamExe')[0])
    except OSError: return None
    return path if path.is_file() else None


def steam_library(game):
    """The Steam library's steamapps folder a game folder is in (…\\steamapps\\common\\<folder>), or None."""
    game = Path(game)
    return game.parent.parent if game.parent.name.lower() == 'common' and game.parent.parent.name.lower() == 'steamapps' else None


def steam_folder(steamapps):
    """The game folder's name in Steam's manifest of the library, or None when the library has no manifest for it."""
    try: text = (Path(steamapps) / f'appmanifest_{APP_ID}.acf').read_text(encoding='utf-8', errors='replace')
    except OSError: return None
    found = re.search(r'"installdir"\s+"([^"]+)"', text)
    return found.group(1) if found else None


def command(game, file_name, steam=steam_exe):
    """(the program and its arguments, the folder to start it in or None, 'steam' or 'direct') to start the game in
    `game` with the commands file `file_name` (in its XEW\\Binaries). A LaunchError says why it can't be started."""
    game = Path(game)
    library = steam_library(game)
    if library is None:
        exe = game / 'XEW' / 'Binaries' / 'Win32' / 'XComEW.exe'
        if not exe.is_file(): raise LaunchError(f'{game} has no XEW\\Binaries\\Win32\\XComEW.exe')
        return [str(exe), f'-EXEC={file_name}'], exe.parent, 'direct'
    runs = steam_folder(library)
    if runs is None: raise LaunchError(f'Steam has no XCOM: Enemy Unknown in {library} (no appmanifest_{APP_ID}.acf)')
    if runs.lower() != game.name.lower():
        raise LaunchError(f'Steam runs {library / "common" / runs}, and the editor installs into {game}: set the '
                          'install to the folder Steam runs')
    program = steam()
    if program is None: raise LaunchError('Steam was not found (no SteamExe in the registry)')
    return [str(program), '-applaunch', APP_ID, f'-EXEC={file_name}'], None, 'steam'


def start(argv, cwd=None):
    """Start the game (or Steam, which starts it) and leave it running on its own."""
    flags = getattr(subprocess, 'DETACHED_PROCESS', 0) | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
    subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=flags, close_fds=True)
