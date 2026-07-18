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
    "a-e": ["make", "cake", "late", "game", "name"],
    "e-e": ["these", "theme", "eve", "gene", "scene"],
    "i-e": ["like", "bike", "time", "mine", "side"],
    "o-e": ["home", "bone", "note", "hope", "rope"],
    "u-e": ["cube", "tune", "huge", "rude", "use"],

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
    # Phase 3
    "j", "v", "w", "x", "y", "z", "qu", "ch", "sh", "th", "ng",
    "ai", "ee", "igh", "oa", "oo", "ar", "or", "ur", "ow", "oi", "ear", "air", "ure", "er",
    # Phase 5a
    "ay", "ou", "ie", "ea", "oy", "ir", "ue", "aw", "wh", "ph", "ew", "oe", "au", "ey",
    "a-e", "e-e", "i-e", "o-e", "u-e",
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
    "h": "h", "b": "b", "f": "f", "l": "l",
    "j": "j", "v": "v", "w": "w", "x": "x", "y": "y", "z": "z", "qu": "qu",
    "ch": "ch", "sh": "sh", "th": "th", "ng": "ng",
    "ai": "ai", "ee": "ee", "igh": "igh", "oa": "oa", "oo": "oo",
    "ar": "ar", "or": "or", "ur": "ur", "ow": "ow", "oi": "oi",
    "ear": "ear", "air": "air", "ure": "ure", "er": "er",
    "ay": "ay", "ou": "ou", "ie": "ie", "ea": "ea", "oy": "oy", "ir": "ir",
    "ue": "ue", "aw": "aw", "wh": "wh", "ph": "ph", "ew": "ew", "oe": "oe",
    "au": "au", "ey": "ey", "a-e": "a-e", "e-e": "e-e", "i-e": "i-e",
    "o-e": "o-e", "u-e": "u-e",
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
