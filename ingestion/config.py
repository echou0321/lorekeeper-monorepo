import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL      = os.environ['DATABASE_URL']
VOYAGE_API_KEY    = os.environ['VOYAGE_API_KEY']
FANDOM_SLUG       = os.environ.get('FANDOM_SLUG', 'one-piece')

EMBEDDING_MODEL      = 'voyage-3'
EMBEDDING_DIMENSIONS = 1024
CHUNK_SIZE           = 450  # target tokens
CHUNK_OVERLAP        = 50
MIN_CHUNK_TOKENS     = 100  # sections smaller than this are kept as-is
TOP_K_CHUNKS         = 8

ARC_SECTION_MAP = {
    'romance dawn arc':        1,
    'orange town arc':         2,
    'syrup village arc':       3,
    'baratie arc':             4,
    'arlong park arc':         5,
    'loguetown arc':           6,
    'reverse mountain arc':    7,
    'whisky peak arc':         8,
    'little garden arc':       9,
    'drum island arc':        10,
    'alabasta arc':           11,
    'jaya arc':               12,
    'skypiea arc':            13,
    'long ring long land arc': 14,
    'water 7 arc':            15,
    'enies lobby arc':        16,
    'post-enies lobby arc':   17,
    'thriller bark arc':      18,
    'sabaody archipelago arc': 19,
    'amazon lily arc':        20,
    'impel down arc':         21,
    'marineford arc':         22,
    'post-war arc':           23,
    'return to sabaody arc':  24,
    'fish-man island arc':    25,
    'punk hazard arc':        26,
    'dressrosa arc':          27,
    'zou arc':                28,
    'whole cake island arc':  29,
    'levely arc':             30,
    'wano country arc':       31,
    'egghead arc':            32,
    'elbaph arc':             33,
}

# Sections whose content warrants a 1-arc spoiler buffer regardless of arc_index
SPOILER_SENSITIVE_PATTERNS = [
    'death',
    'devil fruit awakening',
    'void century',
    'joy boy',
    'im ',
    'imu',
    'identity',
    'real name',
    'true identity',
    'reveal',
    'poneglyph',
    'will of d',
    'ancient weapon',
    'uranus',
    'pluton',
    'poseidon',
]
