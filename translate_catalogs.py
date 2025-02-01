import os
import polib
from deep_translator import GoogleTranslator
from tqdm import tqdm

BASE_DIR = os.path.join(os.path.dirname(__file__), "apc/locale")

for lang_dir in os.listdir(BASE_DIR):
    lang_path = os.path.join(BASE_DIR, lang_dir, "LC_MESSAGES", "apc.po")

    if os.path.isfile(lang_path):  # Ensure the file exists
        print(f"Processing translation for: {lang_dir} ({lang_path})")
        po = polib.pofile(lang_path)
        target_lang = lang_dir.split("_")[0]
        if target_lang == "zh":
            target_lang = "zh-CN"
            translator = GoogleTranslator(source='en', target=target_lang)

        for entry in tqdm(po):
            if entry.msgid and not entry.msgstr:  # Only translate if msgstr is empty
                translated_text = translator.translate(entry.msgid)

        po.save(lang_path)
        print(f"Translation completed for {lang_dir}")

print("All translations are done.")
