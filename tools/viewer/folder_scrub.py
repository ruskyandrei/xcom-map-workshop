"""No folder of this computer in what is shared: a map pack's texts (manager.pack) and a build folder's own manifest
(tools/editor/build.py), which a user may zip and pass on (review finding 14; smaller built maps plan, P1 and P2).

`scrubber` puts a placeholder (<builds>, <install>, ...) in place of each folder it is told of, then anything left
that is shaped like a folder of a computer: a drive's or a network share's absolute path becomes <folder>, and the
name after Users or home <user> (a folder it was not told of, a second drive, an error's words). `scrubbed` passes
every text of a JSON value through one.
"""
from pathlib import Path
import re

# Folders the scrubber was not told of: a drive's or a network share's absolute path, up to the next space or quote,
# and a user's folder under Users or home, whatever comes before it
UNKNOWN_FOLDER = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s"\'<>|]*|\\\\[^\\\s"\'<>|]+\\[^\s"\'<>|]*')
USER_FOLDER = re.compile(r'([\\/](?:users|home)[\\/])[^\\/\s"\'<>|]+', re.IGNORECASE)
# the made-up game folder the editor's own words give as an example (a pack's README: Install.cmd "<it>"), which the
# guard leaves as it is
EXAMPLE_GAME = 'D:\\Steam\\steamapps\\common\\XCom-Enemy-Unknown'
EXAMPLES = re.compile(re.escape(EXAMPLE_GAME))
KEPT = re.compile('\0(\\d+)\0')


def scrubber(roots):
    """A function putting a placeholder (<name>) in place of each folder of `roots` ({name: folder}) in a text, either
    slash and any case, the longest first; then each UNKNOWN_FOLDER becomes <folder> and each USER_FOLDER's name
    <user>, but for the editor's own example (EXAMPLE_GAME). The function's `unknown` counts the texts where that was
    needed."""
    found = sorted(((name, str(Path(root))) for name, root in roots.items() if root and len(str(Path(root))) > 3),
                   key=lambda pair: -len(pair[1]))
    patterns = [(re.compile(r'[\\/]'.join(re.escape(part) for part in re.split(r'[\\/]', text)), re.IGNORECASE), f'<{name}>')
                for name, text in found]

    def scrub(text):
        for pattern, placeholder in patterns:
            text = pattern.sub(lambda _: placeholder, text)
        kept = []
        held = EXAMPLES.sub(lambda m: kept.append(m.group(0)) or f'\0{len(kept) - 1}\0', text)
        guarded = USER_FOLDER.sub(lambda m: m.group(1) + '<user>', UNKNOWN_FOLDER.sub('<folder>', held))
        if guarded != held:
            scrub.unknown += 1
        return KEPT.sub(lambda m: kept[int(m.group(1))], guarded)
    scrub.unknown = 0
    return scrub


def scrubbed(value, scrub):
    """A JSON value with every text in it (keys too) scrubbed."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrubbed(v, scrub) for v in value]
    if isinstance(value, dict):
        return {scrub(k) if isinstance(k, str) else k: scrubbed(v, scrub) for k, v in value.items()}
    return value
