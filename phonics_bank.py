# Phonics word bank for ULS intervention pupils.
# Words are ordered by the ULS teaching progression.
# Each GPC key maps to 5 practice words using only graphemes taught at or before that point.
# Phase 2 words use single-letter graphemes freely (no Phase 3+ digraphs/vowel pairs).

PHONICS_BANK = {
    # ── Phase 2 ────────────────────────────────────────────────────────────────
    # Single-letter graphemes only; common CVC words that feature the target letter.

    "s": ["sat", "sip", "sob", "sun", "set"],
    "a": ["tap", "cat", "hat", "bat", "map"],
    "t": ["top", "tip", "ten", "bit", "pot"],
    "p": ["pet", "pin", "hop", "cap", "pat"],
    "i": ["big", "bit", "dim", "fin", "lip"],
    "n": ["net", "nod", "nip", "nun", "hen"],
    "m": ["mob", "mud", "met", "mop", "him"],
    "d": ["dig", "dot", "den", "dip", "bad"],
    "g": ["got", "gap", "gum", "leg", "pig"],
    "o": ["hop", "dog", "fog", "mop", "sob"],
    "ck": ["sock", "tick", "mock", "dock", "pick"],
    "e": ["set", "pen", "men", "pet", "ten"],
    "u": ["sun", "mug", "sum", "nut", "gun"],
    "r": ["run", "rip", "rot", "rim", "rod"],
    "h": ["hot", "him", "hen", "hip", "hat"],
    "b": ["big", "bad", "bit", "bed", "bus"],
    "f": ["fat", "fin", "fog", "fun", "fed"],
    "l": ["leg", "lid", "lot", "let", "lip"],
    "c": ["cat", "cap", "cod", "cup", "cot"],
    "k": ["kit", "kid", "keg", "kin", "kept"],

    # ── Phase 3 ────────────────────────────────────────────────────────────────
    # New consonant graphemes; all Phase 2 single-letter graphemes now available.

    "j": ["jet", "jam", "jog", "jug", "jab"],
    "v": ["van", "vet", "vim", "vat", "veg"],
    "w": ["wet", "win", "wag", "web", "wig"],
    "x": ["fox", "box", "six", "mix", "fix"],
    "y": ["yet", "yam", "yap", "yes", "yell"],
    "z": ["zip", "zap", "zit", "zen", "zig"],
    "qu": ["quiz", "quit", "quip", "quid", "quill"],
    "ch": ["chip", "chin", "chat", "chop", "rich"],
    "sh": ["ship", "shop", "shed", "fish", "dish"],
    "th": ["thin", "then", "that", "this", "with"],
    "ng": ["ring", "sing", "king", "bang", "long"],

    # Vowel digraphs — from this point each new digraph is available in words.

    "ai": ["rain", "pain", "sail", "tail", "mail"],
    "ee": ["feed", "seed", "feet", "need", "been"],
    "igh": ["night", "light", "high", "sigh", "fight"],
    "oa": ["boat", "coat", "goat", "road", "load"],
    "oo": ["food", "moon", "tool", "boot", "roof"],
    "ar": ["car", "far", "bar", "star", "farm"],
    "or": ["for", "born", "horn", "sort", "storm"],
    "ur": ["burn", "turn", "hurt", "surf", "burst"],
    "ow": ["cow", "now", "how", "town", "down"],
    "oi": ["oil", "foil", "boil", "coin", "join"],
    "ear": ["ear", "fear", "near", "dear", "hear"],
    "air": ["air", "fair", "hair", "pair", "stair"],
    "ure": ["sure", "pure", "cure", "lure", "secure"],
    "er":  ["her", "over", "after", "river", "never"],

    # ── Phase 5a ───────────────────────────────────────────────────────────────
    # New graphemes; all Phase 2 + 3 graphemes now available.

    "ay": ["day", "say", "play", "stay", "way"],
    "ou": ["out", "shout", "cloud", "round", "sound"],
    "ie": ["tie", "pie", "die", "lie", "fries"],
    "ea": ["sea", "tea", "read", "meat", "heat"],
    "oy": ["boy", "toy", "joy", "enjoy", "annoy"],
    "ir": ["bird", "girl", "shirt", "first", "sir"],
    "ue": ["blue", "true", "clue", "glue", "due"],
    "aw": ["paw", "saw", "law", "claw", "draw"],
    "wh": ["when", "which", "whip", "whiz", "whim"],
    "ph": ["dolphin", "orphan", "photo", "alphabet", "sulphur"],
    "ew": ["new", "few", "dew", "grew", "drew"],
    "oe": ["toe", "foe", "doe", "hoe", "roe"],
    "au": ["haul", "fault", "sauce", "launch", "cause"],
    "ey": ["they", "grey", "prey", "obey", "hey"],
    "zh": ["treasure", "measure", "vision", "usual", "visual"],
    "a-e": ["make", "cake", "late", "game", "name"],
    "e-e": ["these", "theme", "eve", "gene", "scene"],
    "i-e": ["like", "bike", "time", "mine", "side"],
    "o-e": ["home", "bone", "note", "hope", "rope"],
    "u-e": ["cube", "tune", "huge", "rude", "use"],

    # ── Y1 National Curriculum (Set 16) ───────────────────────────────────────

    "nk": ["drink", "think", "thank", "sink", "dunk"],
    "ve": ["have", "give", "live", "love", "serve"],

    # ── Phase 4 — review & polysyllabic words (GPC-agnostic) ──────────────────
    # Not tied to a single GPC — a consolidation set drawing on graphemes already taught.

    "p4_gr2":  ["went", "swim", "track", "bend", "lost"],
    "p4_gr3":  ["green", "train", "smart", "growl", "paint"],
    "p4_poly": ["shampoo", "floating", "lunchbox", "starlight", "handstand"],

    # ── Phase 5b — alternative pronunciations (Set 17) ────────────────────────
    # Same grapheme as an earlier phase, but representing a different sound —
    # kept under distinct "_alt" keys so they don't collide with the phase 2/3
    # entries above for the same letter(s).

    "a_alt":  ["acorn", "fast", "wash", "April", "banana"],
    "e_alt":  ["relax", "me", "we", "she", "he"],
    "i_alt":  ["mind", "kind", "find", "rewind", "island"],
    "o_alt":  ["both", "hotel", "open", "go", "pony"],
    "u_alt":  ["unit", "put", "push", "pull", "judo"],
    "ea_e":   ["bread", "dead", "head", "spread", "thread"],
    "ou_alt": ["soup", "could", "mould", "young", "cousin"],
    "y_alt":  ["by", "gym", "very", "cry", "typical"],
    "ch_alt": ["school", "chef", "machine", "chemist", "stomach"],
    "c_alt":  ["city", "cell", "cent", "rice", "face"],
    "g_alt":  ["age", "gem", "giant", "gym", "huge"],

    # ── Phase 5c — alternative spellings ──────────────────────────────────────
    # All Phase 2, 3 and 5a graphemes now available.

    # Alternative consonant spellings
    "tch":    ["catch", "match", "watch", "fetch", "witch"],
    "dge":    ["badge", "fudge", "dodge", "ledge", "bridge"],
    "mb":     ["lamb", "bomb", "climb", "thumb", "comb"],
    "gn":     ["gnaw", "gnat", "gnome", "sign", "gnarl"],
    "kn":     ["knit", "know", "knock", "knee", "knife"],
    "wr":     ["wrap", "wren", "wrong", "write", "wrist"],

    # /ar/ alternatives
    "al_ar":  ["half", "calf", "calm", "palm", "alms"],

    # /or/ alternatives
    "al_or":  ["all", "ball", "call", "fall", "hall"],
    "our_or": ["four", "pour", "your", "course", "source"],
    "augh":   ["caught", "taught", "daughter", "naughty", "haughty"],

    # /ur/ alternatives
    "ear_ur": ["learn", "earth", "heard", "search", "pearl"],
    "or_ur":  ["word", "work", "worm", "world", "worth"],

    # /oo/ (short) alternative
    # Note: oul=/ʊ/ is rare — could/would/should are the main examples.
    "oul_oo": ["could", "would", "should", "couldn't", "wouldn't"],

    # /ai/ alternatives (also taught in Phase 5a; here as alt spellings)
    "ay_ai":  ["day", "play", "stay", "away", "pray"],

    # /ee/ alternatives
    "ea_ee":  ["sea", "read", "dream", "team", "stream"],
    "ie_ee":  ["chief", "field", "shield", "piece", "thief"],
    "ey_ee":  ["key", "monkey", "donkey", "honey", "money"],

    # /igh/ alternatives
    "ie_igh": ["pie", "tie", "die", "lie", "cries"],
    "y_igh":  ["by", "my", "try", "fly", "dry"],

    # /oa/ alternatives
    "ow_oa":  ["low", "show", "grow", "slow", "blow"],
    "oe_oa":  ["toe", "foe", "doe", "hoe", "goes"],

    # /(y)oo/ alternatives
    "ew_yoo": ["few", "new", "stew", "dew", "knew"],
    "ue_yoo": ["cue", "due", "hue", "fuel", "duel"],

    # /oo/ (long) alternatives
    "ue_oo":  ["clue", "blue", "glue", "true", "flue"],
    "ew_oo":  ["blew", "flew", "drew", "grew", "threw"],

    # /sh/ alternatives
    "ti_sh":  ["station", "nation", "action", "fiction", "section"],
    "su_sh":  ["sugar", "sure", "assurance", "insurance", "censure"],
}

PHASE_ORDER = [
    # Phase 2
    "s", "a", "t", "p", "i", "n", "m", "d", "g", "o", "ck", "e", "u", "r", "h", "b", "f", "l",
    "c", "k",
    # Phase 3
    "j", "v", "w", "x", "y", "z", "qu", "ch", "sh", "th", "ng",
    "ai", "ee", "igh", "oa", "oo", "ar", "or", "ur", "ow", "oi", "ear", "air", "ure", "er",
    # Phase 5a
    "ay", "ou", "ie", "ea", "oy", "ir", "ue", "aw", "wh", "ph", "ew", "oe", "au", "ey", "zh",
    "a-e", "e-e", "i-e", "o-e", "u-e",
    # Y1 National Curriculum
    "nk", "ve",
    # Phase 4 review & polysyllabic
    "p4_gr2", "p4_gr3", "p4_poly",
    # Phase 5b alternative pronunciations
    "a_alt", "e_alt", "i_alt", "o_alt", "u_alt", "ea_e", "ou_alt", "y_alt",
    "ch_alt", "c_alt", "g_alt",
    # Phase 5c alternatives
    "tch", "dge", "mb", "gn", "kn", "wr",
    "al_ar", "al_or", "our_or", "augh", "ear_ur", "or_ur", "oul_oo",
    "ay_ai", "ea_ee", "ie_ee", "ey_ee", "ie_igh", "y_igh", "ow_oa", "oe_oa",
    "ew_yoo", "ue_yoo", "ue_oo", "ew_oo", "ti_sh", "su_sh",
]

# Human-readable labels for each GPC key
GPC_LABELS = {
    "s": "s", "a": "a", "t": "t", "p": "p", "i": "i", "n": "n", "m": "m",
    "d": "d", "g": "g", "o": "o", "ck": "ck", "e": "e", "u": "u", "r": "r",
    "h": "h", "b": "b", "f": "f", "l": "l", "c": "c", "k": "k",
    "j": "j", "v": "v", "w": "w", "x": "x", "y": "y", "z": "z", "qu": "qu",
    "ch": "ch", "sh": "sh", "th": "th", "ng": "ng",
    "ai": "ai", "ee": "ee", "igh": "igh", "oa": "oa", "oo": "oo",
    "ar": "ar", "or": "or", "ur": "ur", "ow": "ow", "oi": "oi",
    "ear": "ear", "air": "air", "ure": "ure", "er": "er",
    "ay": "ay", "ou": "ou", "ie": "ie", "ea": "ea", "oy": "oy", "ir": "ir",
    "ue": "ue", "aw": "aw", "wh": "wh", "ph": "ph", "ew": "ew", "oe": "oe",
    "au": "au", "ey": "ey", "zh": "/zh/ (treasure)", "a-e": "a-e", "e-e": "e-e", "i-e": "i-e",
    "o-e": "o-e", "u-e": "u-e",
    "nk": "nk", "ve": "ve",
    "p4_gr2": "Phase 2 review words", "p4_gr3": "Phase 3 review words",
    "p4_poly": "Polysyllabic words",
    "a_alt": "a (alt — wash/April)", "e_alt": "e (alt — relax/me)",
    "i_alt": "i (alt — mind/island)", "o_alt": "o (alt — open/pony)",
    "u_alt": "u (alt — unit/push)", "ea_e": "ea (alt — bread)",
    "ou_alt": "ou (alt — soup/could)", "y_alt": "y (alt — gym/cry)",
    "ch_alt": "ch (alt — school/chef)", "c_alt": "c (alt — city)",
    "g_alt": "g (alt — age/gem)",
    "tch": "tch (/ch/)", "dge": "dge (/j/)", "mb": "mb (/m/)",
    "gn": "gn (/n/)", "kn": "kn (/n/)", "wr": "wr (/r/)",
    "al_ar": "al (/ar/ — half)", "al_or": "al (/or/ — all)",
    "our_or": "our (/or/ — four)", "augh": "augh (/or/ — caught)",
    "ear_ur": "ear (/ur/ — learn)", "or_ur": "or (/ur/ — word)",
    "oul_oo": "oul (/oo/ — could)", "ay_ai": "ay (/ai/ — day)",
    "ea_ee": "ea (/ee/ — sea)", "ie_ee": "ie (/ee/ — chief)",
    "ey_ee": "ey (/ee/ — key)", "ie_igh": "ie (/igh/ — pie)",
    "y_igh": "y (/igh/ — by)", "ow_oa": "ow (/oa/ — low)",
    "oe_oa": "oe (/oa/ — toe)", "ew_yoo": "ew (/yoo/ — few)",
    "ue_yoo": "ue (/yoo/ — cue)", "ue_oo": "ue (/oo/ — clue)",
    "ew_oo": "ew (/oo/ — blew)", "ti_sh": "ti (/sh/ — station)",
    "su_sh": "su (/sh/ — sugar)",
}

# ── Phase → Set groupings, matching the school's ULS spreadsheet ───────────────
# Drives the Class Manager "Phase / Set" picker: choosing a set assigns all of
# its GPCs to a pupil in one go, matching how ULS intervention groups are taught.

PHONICS_SETS = [
    {"phase": "Phase 2", "sets": [
        {"id": "set1", "label": "Set 1", "gpcs": ["s", "a", "t", "p"]},
        {"id": "set2", "label": "Set 2", "gpcs": ["i", "n", "m", "d"]},
        {"id": "set3", "label": "Set 3", "gpcs": ["g", "o", "c", "k"]},
        {"id": "set4", "label": "Set 4", "gpcs": ["ck", "e", "u", "r"]},
        {"id": "set5", "label": "Set 5", "gpcs": ["h", "b", "f", "l"]},
    ]},
    {"phase": "Phase 3", "sets": [
        {"id": "set6",  "label": "Set 6",  "gpcs": ["j", "v", "w", "x"]},
        {"id": "set7",  "label": "Set 7",  "gpcs": ["y", "z", "qu"]},
        {"id": "set8",  "label": "Set 8",  "gpcs": ["ch", "sh", "th", "ng"]},
        {"id": "set9",  "label": "Set 9",  "gpcs": ["ai", "ee", "igh", "oa"]},
        {"id": "set10", "label": "Set 10", "gpcs": ["oo", "ar", "or", "ur"]},
        {"id": "set11", "label": "Set 11", "gpcs": ["ow", "oi", "ear", "air"]},
        {"id": "set12", "label": "Set 12", "gpcs": ["ure", "er"]},
    ]},
    {"phase": "Phase 4", "sets": [
        {"id": "p4_gr2",  "label": "Phase 2 review words", "gpcs": ["p4_gr2"]},
        {"id": "p4_gr3",  "label": "Phase 3 review words", "gpcs": ["p4_gr3"]},
        {"id": "p4_poly", "label": "Polysyllabic words",    "gpcs": ["p4_poly"]},
    ]},
    {"phase": "Phase 5a", "sets": [
        {"id": "set13", "label": "Set 13", "gpcs": ["ay", "ou", "ie", "ea", "oy", "ir", "ue"]},
        {"id": "set14", "label": "Set 14", "gpcs": ["aw", "wh", "ph", "ew", "oe", "au", "ey", "zh"]},
        {"id": "set15", "label": "Set 15", "gpcs": ["a-e", "e-e", "i-e", "o-e", "u-e"]},
    ]},
    {"phase": "Y1 NC", "sets": [
        {"id": "set16", "label": "Set 16", "gpcs": ["nk", "tch", "ve"]},
    ]},
    {"phase": "Phase 5b", "sets": [
        {"id": "set17", "label": "Set 17 (alternative pronunciations)", "gpcs": [
            "a_alt", "e_alt", "i_alt", "o_alt", "u_alt", "ow_oa", "ie_ee", "ea_e",
            "er", "ou_alt", "y_alt", "ch_alt", "c_alt", "g_alt", "ey",
        ]},
    ]},
]


def get_phonics_words(gpcs, bank=None, count=5):
    """Interleave words from each GPC's bank entry to fill `count` slots."""
    bank = bank if bank is not None else PHONICS_BANK
    pools = [bank.get(g, []) for g in gpcs if g in bank]
    if not pools:
        return []
    result, i = [], 0
    while len(result) < count:
        added = False
        for pool in pools:
            if i < len(pool):
                result.append(pool[i])
                added = True
                if len(result) == count:
                    break
        if not added:
            break
        i += 1
    return result
