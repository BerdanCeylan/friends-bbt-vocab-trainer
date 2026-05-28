"""
OCR / Transcription Error Correction System for TV Subtitle Vocabulary

Bu modül, Friends ve Big Bang Theory altyazılarından gelen
yaygın OCR ve otomatik transkripsiyon hatalarını tespit edip düzeltir.

En yaygın sorun: "l" harfinin "i" olarak yanlış tanınması.
Örnek: life → iife, well → weii, really → reaiiy, etc.

Kullanım:
    from scripts.ocr_corrections import correct_word, get_correction_report

    corrected = correct_word("iife")      # → "life"
    corrected = correct_word("weii")      # → "well"
    corrected = correct_word("reaiiy")    # → "really"
"""

import re
from typing import Dict, Optional, Tuple, List

# =============================================================================
# ANA DÜZELTME HARİTASI (Elle doğrulanmış yüksek kaliteli düzeltmeler)
# =============================================================================

# En kritik ve yaygın OCR hataları (l → i karışıklığı başta)
OCR_CORRECTIONS: Dict[str, str] = {
    # === l → i hataları (en yaygın) ===
    "iife": "life",
    "weii": "well",
    "aii": "all",
    "reaiiy": "really",
    "iike": "like",
    "teii": "tell",
    "wouid": "would",
    "couid": "could",
    "shouid": "should",
    "iove": "love",
    "iook": "look",
    "taik": "talk",
    "iet": "let",
    "piease": "please",
    "actuaiiy": "actually",
    "caii": "call",
    "feei": "feel",
    "oniy": "only",
    "peopie": "people",
    "heiio": "hello",
    "whiie": "while",
    "iive": "live",
    "iittie": "little",
    "wiii": "will",
    "stiii": "still",
    "beiieve": "believe",
    "caiiing": "calling",
    "heip": "help",
    "iong": "long",
    "probabiy": "probably",
    "piay": "play",
    "oid": "old",
    "ieft": "left",
    "ieave": "leave",
    "taiking": "talking",
    "iiving": "living",
    "ioved": "loved",
    "iooking": "looking",
    "wouidn": "wouldn",
    "couidn": "couldn",
    "shouidn": "shouldn",
    "iearn": "learn",
    "iearning": "learning",
    "cailed": "called",
    "teiling": "telling",
    "feeiing": "feeling",
    "heiping": "helping",
    "piaying": "playing",
    "waii": "wall",
    "faii": "fall",
    "smaiier": "smaller",
    "reaity": "reality",
    "reai": "real",
    "reaiize": "realize",
    "reaiised": "realised",
    "reaiized": "realized",
    "reaiiy": "really",
    "actuai": "actual",
    "actuaiiy": "actually",
    "naturaiiy": "naturally",
    "personaiiy": "personally",
    "speciaiiy": "specially",
    "especiaiiy": "especially",
    "finaiiy": "finally",
    "originaity": "originality",
    "possibiy": "possibly",
    "incredibiy": "incredibly",
    "terribiy": "terribly",
    "horribiy": "horribly",
    "beautifuily": "beautifully",
    "carefuily": "carefully",
    "hopefuily": "hopefully",
    "successfuiiy": "successfully",
    "wonderfuiiy": "wonderfully",
    "thankfuiiy": "thankfully",
    "fortunatety": "fortunately",
    "unfortunatety": "unfortunately",
    "immediatety": "immediately",
    "absolutety": "absolutely",
    "definiteiy": "definitely",
    "certainiy": "certainly",
    "generaily": "generally",
    "particuiarly": "particularly",
    "especiaily": "especially",
    "basicaity": "basically",
    "technicaily": "technically",
    "practicaity": "practically",
    "actuaily": "actually",

    # === Diğer yaygın OCR hataları ===
    "congratuiations": "congratulations",
    "congratulations": "congratulations",  # zaten doğru
    "apparentiy": "apparently",
    "obviousiy": "obviously",
    "seriousiy": "seriously",
    "curiousiy": "curiously",
    "nervousiy": "nervously",
    "anxiousiy": "anxiously",
    "jealousiy": "jealously",

    # === rn → m, m → rn hataları ===
    "moming": "morning",
    "mornings": "mornings",
    "tuming": "turning",
    "tum": "turn",
    "tums": "turns",
    "retum": "return",
    "retums": "returns",
    "retumed": "returned",
    "modem": "modern",
    "com": "com",           # internet com'u etkilemesin diye dikkat

    # === Diğer garip hatalar ===
    "wouidn": "wouldn",
    "couidn": "couldn",
    "shouidn": "shouldn",
    "wouidn't": "wouldn't",
    "couidn't": "couldn't",
    "shouidn't": "shouldn't",

    # === Ekstra tespit edilenler ===
    "iittie": "little",
    "iive": "live",
    "iiving": "living",
    "ioved": "loved",
    "iook": "look",
    "iooking": "looking",
    "iooked": "looked",
    "taik": "talk",
    "taiking": "talking",
    "taiked": "talked",
    "iet": "let",
    "ietting": "letting",
    "piease": "please",
    "pieased": "pleased",
    "caii": "call",
    "caiiing": "calling",
    "cailed": "called",
    "feei": "feel",
    "feeiing": "feeling",
    "feels": "feels",
    "heip": "help",
    "heiping": "helping",
    "heiped": "helped",
    "iong": "long",
    "ionger": "longer",
    "probabiy": "probably",
    "piay": "play",
    "piaying": "playing",
    "piayed": "played",
    "oid": "old",
    "oider": "older",
    "ieft": "left",
    "ieave": "leave",
    "ieaving": "leaving",
    "iearn": "learn",
    "iearning": "learning",
    "ieamed": "learned",
    "heiio": "hello",
    "whiie": "while",
}

# Regex bazlı daha geniş düzeltmeler (güvenli olanlar)
REGEX_CORRECTIONS = [
    # l → i hatalarını daha geniş yakala (ama dikkatli ol)
    (r'\b(\w*?)ii(\w*?)\b', lambda m: m.group(1) + 'll' + m.group(2) if len(m.group(0)) > 3 else m.group(0)),
    (r'\b(\w*?)ie(\w*?)\b', lambda m: m.group(1) + 'le' + m.group(2) if len(m.group(0)) > 3 else m.group(0)),
]

# =============================================================================
# ANA FONKSİYONLAR
# =============================================================================

def correct_word(word: str, aggressive: bool = False) -> Tuple[str, Optional[str]]:
    """
    Bir kelimeyi OCR hatalarından temizler.

    Returns:
        (düzeltilmiş_kelime, orijinal_kelime_eğer_değiştiyse)
    """
    original = word
    w = word.lower().strip()

    # 1. Direkt harita kontrolü (en güvenilir)
    if w in OCR_CORRECTIONS:
        corrected = OCR_CORRECTIONS[w]
        return corrected, original if corrected != original else None

    # 2. Basit regex düzeltmeleri (dikkatli)
    if aggressive:
        for pattern, replacement in REGEX_CORRECTIONS:
            new_w = re.sub(pattern, replacement, w)
            if new_w != w:
                return new_w, original if new_w != original else None

    return w, None


def batch_correct_words(words: List[str]) -> Dict[str, str]:
    """
    Birden fazla kelimeyi toplu düzeltir.
    Returns: {orijinal: düzeltilmiş} sadece değişenler için
    """
    corrections = {}
    for word in words:
        corrected, original = correct_word(word)
        if original:
            corrections[word] = corrected
    return corrections


def get_correction_report() -> Dict:
    """Mevcut düzeltme haritasının istatistiklerini verir."""
    return {
        "total_rules": len(OCR_CORRECTIONS),
        "most_frequent_targets": sorted(
            set(OCR_CORRECTIONS.values()),
            key=lambda x: list(OCR_CORRECTIONS.values()).count(x),
            reverse=True
        )[:15]
    }


if __name__ == "__main__":
    # Test
    test_words = [
        "iife", "weii", "aii", "reaiiy", "wouid", "couid",
        "teii", "iove", "iook", "piease", "actuaiiy", "heiio",
        "life", "well", "all", "really", "would", "could"  # doğru olanlar
    ]

    print("OCR Correction Test:\n")
    for w in test_words:
        corrected, orig = correct_word(w)
        status = "✓" if corrected == w else f"→ {corrected}"
        print(f"{w:15} {status}")
