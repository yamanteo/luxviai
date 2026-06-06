"""Read-only Lux Visual System style registry scaffold."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List


LUX_VISUAL_METADATA = {
    "lux_amber_accent_color": "#ab6b0c",
    "default_line_density": "low",
    "signature_note": "Place a subtle Luxviai signature at the right bottom when visual generation is implemented.",
    "image_generation_enabled": False,
    "ambrosia_negative_constraints": ["no_city", "no_street", "no_room", "no_building", "no_sign", "no_letters"],
    "lux_special_visual_rules": [
        "Visual types are open-ended.",
        "Lux is a visual spirit/state language, not a fixed place.",
        "Users may provide explicit style ratios.",
        "The system may suggest adaptive read-only ratios by scene.",
        "Used style ratios can be displayed in preview.",
        "Right-bottom Luxviai signature is default in preview.",
        "Line density defaults to low.",
        "Too many lines can make the image feel overdrawn.",
        "Ambrosia should avoid city, room, building, sign, and readable text scenes.",
        "Dream Scene details should be added to the existing scene instead of rebuilding it.",
    ],
}


def _style(
    style_id: str,
    display_name: str,
    group: str,
    description: str,
    default_ratio: float = 0.12,
    max_ratio: float = 0.75,
    compatible_with: List[str] | None = None,
    caution: str = "Read-only preview layer; no image generation is performed.",
    aliases: List[str] | None = None,
) -> Dict[str, Any]:
    return {
        "id": style_id,
        "display_name": display_name,
        "group": group,
        "category": group,
        "description": description,
        "default_ratio": default_ratio,
        "min_ratio": 0.0,
        "max_ratio": max_ratio,
        "compatible_with": compatible_with or [],
        "caution": caution,
        "aliases": aliases or [],
        "read_only": True,
    }


_STYLE_DEFINITIONS = [
    _style("lux_signature", "Lux Signature", "main_visual_modes", "Luxviai signature language with restrained amber accent.", 0.25, 1.0, ["lux_amber_accent", "normal_real_clean"], "Keep signature subtle and right-bottom.", ["lux tarzi", "luxviai", "imza", "signature", "luxviai signature"]),
    _style("normal_real_clean", "Normal / Real / Clean", "main_visual_modes", "Clean realistic baseline with minimal stylization.", 0.55, 1.0, ["lux_signature", "film_grain"], "Avoid over-processing faces or products.", ["normal", "real", "clean", "temiz", "gercekci", "normal real clean"]),
    _style("custom_blend", "Custom Blend", "main_visual_modes", "User-defined style mixture preview.", 0.2, 1.0, ["pixel", "watercolor", "oil_paint"], "Keep ratios explicit before real generation.", ["custom", "blend", "karisim", "custom blend"]),
    _style("lux_ambrosia", "Lux Ambrosia", "main_visual_modes", "Inner-state visual language with black velvet, amber light, platinum glyphs, and haze.", 0.35, 1.0, ["lux_amber_accent", "soft_neon", "dreamcore"], "Ambrosia is not a city, room, building, sign, or text scene.", ["ambrosia", "lux ambrosia", "ambrosia hissi"]),
    _style("dream_scene", "Dream Scene", "main_visual_modes", "Dream-state scene language for symbolic visual planning.", 0.35, 1.0, ["dreamcore", "film_grain", "watercolor"], "Keep scene readable and preserve locked details.", ["ruya", "ruya sahnesi", "dream", "dream scene", "sahne"]),
    _style("scene_lock", "Scene Lock", "main_visual_modes", "Preserve existing scene elements while previewing new details.", 0.18, 1.0, ["dream_scene", "camera_angle_memory"], "New details should not rebuild the scene.", ["scene lock", "sahne kilidi", "sahneyi koru", "koru"]),
    _style("visual_memory", "Visual Memory", "main_visual_modes", "Read-only visual preference signal layer.", 0.16, 0.8, ["lux_signature", "style_ratio"], "No memory write is performed in scaffold.", ["visual memory", "gorsel hafiza", "gorsel tercih"]),
    _style("style_ratio", "Style Ratio", "main_visual_modes", "Explicit or adaptive ratio preview for style mixing.", 0.14, 1.0, ["custom_blend"], "Ratios are preview-only.", ["style ratio", "oran", "stil orani"]),
    _style("emotional_state_visual", "Emotional State Visual", "main_visual_modes", "Emotion-to-visual preview layer.", 0.22, 0.9, ["lux_ambrosia", "dream_emotion_light"], "Keep sensitive feelings summarized safely.", ["emotional state", "ic durum", "duygu gorseli", "ic durum gorsellestirme"]),
    _style("dreamcore_surrealism", "Dreamcore Surrealism", "main_visual_modes", "Dreamcore plus surreal symbolic scene language.", 0.24, 0.8, ["dream_scene", "surrealism"], "Preserve subject clarity.", ["dreamcore surrealism", "surreal dreamcore"]),
    _style("pixel", "Pixel", "paint_surface_layers", "Pixel-art or pixel texture influence.", 0.2, 0.7, ["custom_blend", "vintage_poster"], "High ratios may reduce realism.", ["pixel", "piksel"]),
    _style("watercolor", "Sulu Boya", "paint_surface_layers", "Soft watercolor texture influence.", 0.2, 0.8, ["dream_scene", "monochrome_organic"], "Avoid muddy low-contrast blends.", ["watercolor", "sulu boya", "suluboya"]),
    _style("oil_paint", "Yagli Boya", "paint_surface_layers", "Oil-paint texture and brushwork influence.", 0.2, 0.8, ["custom_blend", "film_grain"], "Use carefully with clean realism.", ["yagli boya", "oil", "oil paint"]),
    _style("digital_paint", "Digital Paint", "paint_surface_layers", "Controlled digital paint surface.", 0.18, 0.7, ["custom_blend", "soft_neon"], aliases=["digital paint", "dijital boya"]),
    _style("matte_paint_texture", "Mat Boya Dokusu", "paint_surface_layers", "Muted matte paint surface.", 0.14, 0.6, ["paper_texture"], aliases=["mat boya", "mat boya dokusu", "matte paint"]),
    _style("fine_brush_texture", "Ince Firca Dokusu", "paint_surface_layers", "Fine brush texture preview.", 0.12, 0.55, ["oil_paint", "watercolor"], aliases=["ince firca", "firca dokusu", "fine brush"]),
    _style("controlled_texture", "Kontrollu Doku", "paint_surface_layers", "Restrained texture layer for readable images.", 0.12, 0.5, ["normal_real_clean"], aliases=["kontrollu doku", "controlled texture"]),
    _style("paper_texture", "Paper Texture", "paint_surface_layers", "Subtle paper grain surface.", 0.12, 0.45, ["watercolor", "poster_print_texture"], aliases=["paper texture", "kagit dokusu"]),
    _style("poster_print_texture", "Poster Print Texture", "paint_surface_layers", "Printed poster surface preview.", 0.16, 0.6, ["vintage_poster", "paper_texture"], aliases=["poster print texture", "poster baski"]),
    _style("vintage_poster", "Vintage Afis Dokusu", "paint_surface_layers", "Poster-like vintage composition and surface preview.", 0.2, 0.7, ["film_grain", "pixel"], "Text rendering is future-only.", ["vintage", "poster", "vintage poster", "vintage afis"]),
    _style("retro_print_feel", "Retro Baski Hissi", "paint_surface_layers", "Retro printed material feeling.", 0.16, 0.6, ["film_grain", "retro_brown"], aliases=["retro baski", "retro renk paleti", "retro print"]),
    _style("film_grain", "Film Grain", "paint_surface_layers", "Subtle film grain and analog texture.", 0.16, 0.5, ["normal_real_clean", "vintage_poster"], "Keep grain subtle.", ["film grain", "grain", "gren"]),
    _style("analog_blur", "Analog Blur", "paint_surface_layers", "Soft analog blur preview.", 0.1, 0.35, ["film_grain"], aliases=["analog blur", "analog bulaniklik"]),
    _style("post_ai_authenticity", "Post-AI Authenticity", "paint_surface_layers", "Lightly imperfect human-touch texture.", 0.12, 0.5, ["controlled_texture"], "Avoid fake artifact overload.", ["post-ai authenticity", "post ai authenticity", "insan dokunusu"]),
    _style("human_touch_imperfection", "Hafif Kusur / Insan Dokunusu", "paint_surface_layers", "Small imperfections that prevent sterile output.", 0.1, 0.35, ["post_ai_authenticity"], aliases=["hafif kusur", "insan dokunusu"]),
    _style("lux_amber_accent", "Lux Amber Accent #ab6b0c", "light_layers", "Lux amber accent color #ab6b0c.", 0.12, 0.45, ["lux_signature", "lux_ambrosia"], "Use as an accent, not a full wash.", ["amber", "lux amber", "lux amber accent", "#ab6b0c"]),
    _style("dream_emotion_light", "Duygu Isik Katmani", "light_layers", "Emotion-linked light layer.", 0.16, 0.6, ["lux_ambrosia"], aliases=["duygu isik", "duygu isik katmani"]),
    _style("atmospheric_light", "Atmosferik Isik", "light_layers", "Soft atmospheric light layer.", 0.16, 0.65, ["haze", "soft_neon"], aliases=["atmosferik isik", "atmospheric light"]),
    _style("glow", "Glow", "light_layers", "Gentle glow layer.", 0.12, 0.5, ["soft_neon"], "Avoid excessive bloom.", ["glow", "parlama"]),
    _style("bright_glow", "Parlayan Isik", "light_layers", "Visible but controlled bright light.", 0.12, 0.5, ["glow"], "Do not overpower subject clarity.", ["parlayan isik", "bright glow"]),
    _style("soft_neon", "Soft Neon", "light_layers", "Soft neon rim or atmosphere influence.", 0.18, 0.6, ["lux_ambrosia", "dreamcore"], "Avoid excessive bloom.", ["soft neon", "neon"]),
    _style("dim_neon", "Los Neon", "light_layers", "Dim neon whisper layer.", 0.12, 0.4, ["soft_neon"], aliases=["los neon", "dim neon"]),
    _style("neon_whisper", "Neon Fisiltisi", "light_layers", "Nearly silent neon accent.", 0.08, 0.25, ["dim_neon"], aliases=["neon fisiltisi", "neon whisper"]),
    _style("moon_cream_halo", "Moon Cream Halo", "light_layers", "Cream moon-halo light.", 0.12, 0.4, ["cream_moon_halo"], aliases=["moon cream halo", "krem ay halesi"]),
    _style("warm_window_light", "Sicak Pencere Isigi", "light_layers", "Warm window light preview.", 0.12, 0.45, ["atmospheric_light"], aliases=["sicak pencere isigi", "window light"]),
    _style("inner_glow", "Icten Isildama", "light_layers", "Light that appears to come from within.", 0.14, 0.5, ["lux_ambrosia"], aliases=["icten isildama", "inner glow"]),
    _style("centered_light", "Merkezli Isik", "light_layers", "Centered light emphasis.", 0.1, 0.45, ["selected_object_focus"], aliases=["merkezli isik", "centered light"]),
    _style("edge_leak_light", "Kenardan Sizan Isik", "light_layers", "Light leaking from an edge.", 0.1, 0.4, ["negative_space"], aliases=["kenardan sizan isik", "edge light"]),
    _style("light_bokeh", "Hafif Bokeh", "light_layers", "Light bokeh layer.", 0.08, 0.35, ["soft_bokeh"], aliases=["hafif bokeh", "bokeh"]),
    _style("soft_bokeh", "Yumusak Bokeh", "light_layers", "Soft bokeh layer.", 0.08, 0.35, ["light_bokeh"], aliases=["yumusak bokeh", "soft bokeh"]),
    _style("dream_layer", "Ruya Katmani", "dream_emotion_atmosphere_layers", "Dream layer over scene state.", 0.16, 0.7, ["dream_scene"], aliases=["ruya katmani"]),
    _style("dreamcore", "Dreamcore", "dream_emotion_atmosphere_layers", "Surreal dreamlike atmosphere preview.", 0.24, 0.8, ["dream_scene", "soft_neon"], "Preserve subject clarity.", ["dreamcore"]),
    _style("surrealism", "Surrealizm", "dream_emotion_atmosphere_layers", "Surreal symbolic distortion layer.", 0.18, 0.7, ["dreamcore_surrealism"], aliases=["surrealism", "surrealizm"]),
    _style("quiet_trance", "Sessiz Trans Hali", "dream_emotion_atmosphere_layers", "Quiet trance-state atmosphere.", 0.12, 0.5, ["haze"], aliases=["sessiz trans"]),
    _style("haze", "Sis / Haze", "dream_emotion_atmosphere_layers", "Soft mist or haze layer.", 0.14, 0.6, ["atmospheric_light"], aliases=["sis", "haze", "sis haze"]),
    _style("memory_slip", "Hafiza Kaymasi", "dream_emotion_atmosphere_layers", "Memory-slip atmosphere.", 0.1, 0.45, ["dream_scene"], aliases=["hafiza kaymasi"]),
    _style("memory_reflection", "Hafiza Yansimasi", "dream_emotion_atmosphere_layers", "Memory reflection surface.", 0.1, 0.45, ["wet_reflection"], aliases=["hafiza yansimasi"]),
    _style("wet_reflection", "Islak Yansima", "dream_emotion_atmosphere_layers", "Wet reflection preview.", 0.12, 0.5, ["memory_reflection"], aliases=["islak yansima", "wet reflection"]),
    _style("soft_distance", "Yumusak Mesafe", "dream_emotion_atmosphere_layers", "Soft spatial distance feeling.", 0.1, 0.4, ["negative_space"], aliases=["yumusak mesafe"]),
    _style("spiritual_closeness", "Ruhani Yakinlik", "dream_emotion_atmosphere_layers", "Spiritual closeness atmosphere.", 0.12, 0.45, ["lux_ambrosia"], aliases=["ruhani yakinlik"]),
    _style("protective_darkness", "Koruyucu Karanlik", "dream_emotion_atmosphere_layers", "Protective darkness around the emotional center.", 0.14, 0.5, ["black_velvet"], aliases=["koruyucu karanlik"]),
    _style("sad_warmth", "Huzunlu Sicaklik", "dream_emotion_atmosphere_layers", "Warm melancholy tone.", 0.12, 0.45, ["lux_amber_accent"], aliases=["huzunlu sicaklik"]),
    _style("timeless_feel", "Zamansizlik Hissi", "dream_emotion_atmosphere_layers", "Timeless scene feeling.", 0.1, 0.45, ["dream_scene"], aliases=["zamansizlik"]),
    _style("ambrosia_emotional_texture", "Ambrosia Emotional Texture", "dream_emotion_atmosphere_layers", "Ambrosia emotional texture layer.", 0.18, 0.7, ["lux_ambrosia"], aliases=["ambrosia emotional texture"]),
    _style("silent_glyph", "Sessiz Glyph", "glyph_symbol_signal_layers", "Quiet glyph signal layer.", 0.08, 0.3, ["micro_glyph"], "Keep glyphs sparse.", ["sessiz glyph", "sessiz sembol", "glyph"]),
    _style("micro_glyph", "Micro Glyph", "glyph_symbol_signal_layers", "Tiny symbolic glyph texture language.", 0.08, 0.35, ["lux_signature", "dreamcore"], "Avoid clutter and overdrawn lines.", ["micro glyph", "mikro sembol"]),
    _style("silent_symbol_layer", "Sessiz Sembol Katmani", "glyph_symbol_signal_layers", "Silent symbol layer.", 0.08, 0.3, ["silent_glyph"], "Symbols should remain subtle.", ["sessiz sembol katmani", "sessiz sembol"]),
    _style("signal_layer", "Sinyal Katmani", "glyph_symbol_signal_layers", "Signal texture layer.", 0.08, 0.35, ["digital_sub_vibration"], aliases=["sinyal katmani", "signal layer"]),
    _style("thin_symbolic_marks", "Ince Sembolik Isaretler", "glyph_symbol_signal_layers", "Thin symbolic mark layer.", 0.06, 0.25, ["micro_glyph"], aliases=["ince sembolik isaretler"]),
    _style("archetypal_symbols", "Arketipsel Semboller", "glyph_symbol_signal_layers", "Archetypal symbolic hints.", 0.06, 0.25, ["silent_glyph"], aliases=["arketipsel semboller"]),
    _style("digital_sub_vibration", "Dijital Alt Titresim", "glyph_symbol_signal_layers", "Low digital vibration signal.", 0.06, 0.25, ["signal_layer"], aliases=["dijital alt titresim"]),
    _style("barely_visible_marks", "Neredeyse Gorunmez Isaretler", "glyph_symbol_signal_layers", "Almost invisible marks.", 0.05, 0.2, ["micro_glyph"], aliases=["neredeyse gorunmez isaretler"]),
    _style("lux_private_sign_language", "Kopyalanmamis Ozel Lux Isaret Dili", "glyph_symbol_signal_layers", "Private Lux sign-language preview scaffold.", 0.05, 0.2, ["lux_signature"], "No real identity or secret data is stored.", ["lux isaret dili", "ozel lux isaret dili"]),
    _style("platinum_thin_line", "Platin Ince Cizgi #C0C0C0", "glyph_symbol_signal_layers", "Platinum thin line color #C0C0C0.", 0.06, 0.25, ["micro_line"], aliases=["platin cizgi", "platin ince cizgi", "#c0c0c0"]),
    _style("rare_direction_lines", "Cok Az Kullanilan Yon Cizgileri", "glyph_symbol_signal_layers", "Rare directional line hints.", 0.04, 0.18, ["minimal_line"], aliases=["yon cizgileri"]),
    _style("minimal_line", "Minimal Cizgi", "line_layers", "Minimal line layer.", 0.08, 0.35, ["low_line_density"], aliases=["minimal cizgi"]),
    _style("thin_line", "Ince Cizgi", "line_layers", "Thin line layer.", 0.08, 0.35, ["minimal_line"], aliases=["ince cizgi"]),
    _style("micro_line", "Mikro Cizgi", "line_layers", "Micro line layer.", 0.05, 0.25, ["thin_line"], aliases=["mikro cizgi", "micro line"]),
    _style("sharp_line", "Keskin Cizgi", "line_layers", "Sharp line layer.", 0.06, 0.3, ["thin_line"], aliases=["keskin cizgi"]),
    _style("organic_line", "Organik Cizgi", "line_layers", "Organic contour line.", 0.08, 0.35, ["monochrome_organic"], aliases=["organik cizgi", "organik kontur"]),
    _style("quiet_contour", "Sessiz Kontur", "line_layers", "Quiet contour line.", 0.06, 0.25, ["organic_line"], aliases=["sessiz kontur"]),
    _style("low_line_density", "Cok Dusuk Cizgi Yogunlugu", "line_layers", "Very low line density default.", 0.08, 0.25, ["minimal_line"], "Default Lux setting.", ["dusuk cizgi", "cok dusuk cizgi yogunlugu"]),
    _style("sky_signal_short_line", "Gokyuzu/Sinyal Alaninda Kisa Cizgi", "line_layers", "Short sky/signal-area lines.", 0.04, 0.18, ["signal_layer"], aliases=["gokyuzu kisa cizgi"]),
    _style("dense_line_user_mode", "Kullanici Isterse Yogun Cizgi Modu", "line_layers", "Optional dense line mode only when requested.", 0.02, 0.45, ["sharp_line"], "Use only when explicitly requested.", ["yogun cizgi", "dense line"]),
    _style("black_velvet", "Siyah Kadife #0A0A0A", "color_tone_layers", "Black velvet background #0A0A0A.", 0.18, 0.8, ["lux_ambrosia"], aliases=["siyah kadife", "#0a0a0a"]),
    _style("platinum_gray", "Platin Gri #C0C0C0", "color_tone_layers", "Platinum gray #C0C0C0.", 0.08, 0.35, ["platinum_thin_line"], aliases=["platin gri", "#c0c0c0"]),
    _style("cream_moon_halo", "Krem Ay Halesi", "color_tone_layers", "Cream moon halo tone.", 0.1, 0.4, ["moon_cream_halo"], aliases=["krem ay halesi"]),
    _style("retro_brown", "Solmus Retro Kahve #8B5A2B", "color_tone_layers", "Faded retro brown #8B5A2B.", 0.08, 0.35, ["retro_print_feel"], aliases=["retro kahve", "#8b5a2b"]),
    _style("vintage_warm_tones", "Vintage Sicak Tonlar", "color_tone_layers", "Vintage warm tones.", 0.12, 0.5, ["vintage_poster"], aliases=["vintage sicak tonlar"]),
    _style("monochrome_organic", "Monochrome Organic", "color_tone_layers", "Muted organic monochrome texture.", 0.18, 0.7, ["watercolor", "micro_glyph"], "Avoid flat one-note palettes.", ["monochrome", "organic", "organik", "monokrom", "monochrome organic"]),
    _style("matte_red", "Mat Kirmizi", "color_tone_layers", "Muted matte red.", 0.06, 0.25, ["vintage_warm_tones"], aliases=["mat kirmizi"]),
    _style("broken_white", "Kirik Beyaz", "color_tone_layers", "Broken white tone.", 0.08, 0.3, ["cream_moon_halo"], aliases=["kirik beyaz"]),
    _style("dim_blue", "Los Mavi", "color_tone_layers", "Dim blue tone.", 0.08, 0.35, ["night_navy"], aliases=["los mavi"]),
    _style("night_navy", "Gece Laciverti", "color_tone_layers", "Night navy tone.", 0.12, 0.5, ["black_velvet"], aliases=["gece laciverti"]),
    _style("dusty_gold", "Tozlu Altin", "color_tone_layers", "Dusty gold accent.", 0.08, 0.3, ["lux_amber_accent"], aliases=["tozlu altin"]),
    _style("dark_glass_feel", "Koyu Cam Hissi", "color_tone_layers", "Dark glass tone.", 0.08, 0.3, ["black_velvet"], aliases=["koyu cam"]),
    _style("soft_sun_tone", "Goz Almayan Gunes Tonu", "color_tone_layers", "Soft non-glare sun tone.", 0.08, 0.3, ["lux_amber_accent"], aliases=["goz almayan gunes"]),
    _style("close_up", "Yakin Plan", "composition_camera_layers", "Close-up composition.", 0.1, 0.5, ["selected_object_focus"], aliases=["yakin plan", "close up"]),
    _style("wide_shot", "Uzak Plan", "composition_camera_layers", "Wide shot composition.", 0.1, 0.5, ["negative_space"], aliases=["uzak plan", "wide shot"]),
    _style("pan", "Pan", "composition_camera_layers", "Pan camera hint.", 0.06, 0.3, ["camera_angle_memory"], aliases=["pan"]),
    _style("tilt", "Tilt", "composition_camera_layers", "Tilt camera hint.", 0.06, 0.3, ["camera_angle_memory"], aliases=["tilt"]),
    _style("zoom", "Zoom", "composition_camera_layers", "Zoom camera hint.", 0.06, 0.3, ["camera_angle_memory"], aliases=["zoom"]),
    _style("misty_field", "Hafif Sisli Alan", "composition_camera_layers", "Light misty field.", 0.1, 0.4, ["haze"], aliases=["hafif sisli alan"]),
    _style("negative_space", "Negatif Bosluk", "composition_camera_layers", "Negative space composition.", 0.12, 0.5, ["wide_shot"], aliases=["negatif bosluk", "negative space"]),
    _style("off_center_composition", "Merkez Disi Kompozisyon", "composition_camera_layers", "Off-center composition.", 0.1, 0.45, ["negative_space"], aliases=["merkez disi"]),
    _style("right_bottom_signature", "Sag Alt Luxviai Imzasi", "composition_camera_layers", "Right-bottom Luxviai signature placement.", 0.08, 0.25, ["lux_signature"], "Signature stays subtle.", ["sag alt luxviai imzasi", "luxviai signature"]),
    _style("selected_object_focus", "Secilmis Obje Odagi", "composition_camera_layers", "Selected object focus.", 0.1, 0.45, ["close_up"], aliases=["obje odagi", "selected object"]),
    _style("depth_relation", "Uzak/Orta/Yakin Iliski", "composition_camera_layers", "Far/mid/near relation.", 0.1, 0.45, ["wide_shot"], aliases=["uzak orta yakin"]),
    _style("object_position_relation", "Obje Konum Iliskisi", "composition_camera_layers", "Object position relation.", 0.08, 0.4, ["scene_lock"], aliases=["obje konum"]),
    _style("camera_angle_memory", "Kamera Acisi Hafizasi", "composition_camera_layers", "Camera angle memory preview.", 0.08, 0.35, ["scene_lock"], "No memory write is performed.", ["kamera acisi", "kamera acisi hafizasi"]),
    _style("soft_motion_smear", "Soft Motion Smear", "composition_camera_layers", "Subtle motion smear preview.", 0.06, 0.3, ["analog_blur"], aliases=["soft motion smear", "hareket izi"]),
]

_STYLE_GROUPS = [
    "main_visual_modes",
    "paint_surface_layers",
    "light_layers",
    "dream_emotion_atmosphere_layers",
    "glyph_symbol_signal_layers",
    "line_layers",
    "color_tone_layers",
    "composition_camera_layers",
    "lux_special_visual_rules",
]


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return (
        text.lower()
        .replace("\u0131", "i")
        .replace("\u0130", "i")
        .replace("\u015f", "s")
        .replace("\u011f", "g")
        .replace("\u00fc", "u")
        .replace("\u00f6", "o")
        .replace("\u00e7", "c")
    )


def visual_style_registry() -> Dict[str, Any]:
    styles = [dict(style) for style in _STYLE_DEFINITIONS]
    grouped_styles = {
        group: [dict(style) for style in styles if style.get("group") == group]
        for group in _STYLE_GROUPS
        if group != "lux_special_visual_rules"
    }
    grouped_styles["lux_special_visual_rules"] = [
        {"id": f"rule_{index + 1}", "description": rule, "read_only": True}
        for index, rule in enumerate(LUX_VISUAL_METADATA["lux_special_visual_rules"])
    ]
    return {
        "styles": styles,
        "groups": grouped_styles,
        "group_names": list(_STYLE_GROUPS),
        "metadata": dict(LUX_VISUAL_METADATA),
        "read_only": True,
        "image_generation_performed": False,
        "memory_write_performed": False,
        "file_written": False,
    }


def _style_map() -> Dict[str, Dict[str, Any]]:
    return {style["id"]: style for style in visual_style_registry()["styles"]}


def _alias_map() -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for style in visual_style_registry()["styles"]:
        style_id = style["id"]
        names = [style_id, style_id.replace("_", " "), style["display_name"], *style.get("aliases", [])]
        for name in names:
            normalized = _normalize_text(str(name)).replace("_", " ").strip()
            if normalized:
                aliases[normalized] = style_id
                aliases[normalized.replace(" ", "_")] = style_id
    return aliases


def _style_for_alias(value: str) -> str:
    normalized = _normalize_text(value).replace("_", " ").strip()
    aliases = _alias_map()
    if normalized in aliases:
        return aliases[normalized]
    if normalized.replace(" ", "_") in aliases:
        return aliases[normalized.replace(" ", "_")]
    for alias, style_id in aliases.items():
        if alias and alias in normalized:
            return style_id
    return ""


def _detect_styles(prompt: str, requested_styles: List[str]) -> List[str]:
    normalized = _normalize_text(prompt)
    detected: List[str] = []
    for requested_style in requested_styles:
        style_id = _style_for_alias(requested_style)
        if style_id in _style_map() and style_id not in detected:
            detected.append(style_id)
    for alias, style_id in _alias_map().items():
        if alias and alias.replace("_", " ") in normalized and style_id not in detected:
            detected.append(style_id)
    if not detected:
        detected = ["normal_real_clean", "lux_signature", "lux_amber_accent"]
    return detected


def _explicit_ratio(prompt: str, style_id: str) -> float | None:
    normalized = _normalize_text(prompt)
    style = _style_map().get(style_id, {})
    aliases = [style_id.replace("_", " "), str(style.get("display_name", "")), *style.get("aliases", [])]
    for alias in aliases:
        alias = _normalize_text(alias)
        pattern = rf"%\s*(\d+)\s*{re.escape(alias)}|(\d+)\s*%\s*{re.escape(alias)}"
        match = re.search(pattern, normalized)
        if match:
            value = next(group for group in match.groups() if group)
            return max(0.0, min(1.0, int(value) / 100))
    return None


def preview_visual_style(prompt: str, requested_styles: List[str] | None = None, mode: str = "") -> Dict[str, Any]:
    styles_by_id = _style_map()
    detected_ids = _detect_styles(prompt, requested_styles or [])
    suggested_styles = [styles_by_id[style_id] for style_id in detected_ids if style_id in styles_by_id]
    style_mix_preview = []
    for style in suggested_styles:
        explicit_ratio = _explicit_ratio(prompt, style["id"])
        ratio = explicit_ratio if explicit_ratio is not None else style["default_ratio"]
        ratio = max(float(style["min_ratio"]), min(float(style["max_ratio"]), ratio))
        style_mix_preview.append(
            {
                "style_id": style["id"],
                "display_name": style["display_name"],
                "ratio": ratio,
                "read_only": True,
            }
        )
    normalized = _normalize_text(prompt)
    if any(word in normalized for word in ["ruya", "dream", "sahne"]):
        detected_visual_intent = "dream_scene_preview"
    elif any(word in normalized for word in ["ambrosia", "his", "hissi"]):
        detected_visual_intent = "ambrosia_style_preview"
    elif any(word in normalized for word in ["cv", "rapor", "sunum"]):
        detected_visual_intent = "workspace_visual_style_preview"
    else:
        detected_visual_intent = "style_preview"
    return {
        "prompt": prompt or "",
        "mode": mode or "visual_style_preview",
        "detected_visual_intent": detected_visual_intent,
        "suggested_styles": suggested_styles,
        "style_mix_preview": style_mix_preview,
        "signature_default": True,
        "lux_metadata": dict(LUX_VISUAL_METADATA),
        "image_generation_performed": False,
        "read_only": True,
        "memory_write_performed": False,
        "file_written": False,
        "safety_note": "Read-only visual style preview only; no image API call or file generation is performed.",
    }
