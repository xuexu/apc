"""
Translate data in .po files to their target language with Google Translate and polib
"""

import os
import time
from pathlib import Path

import polib
from deep_translator import GoogleTranslator
from tqdm import tqdm

from apc.logging_config import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent / "apc" / "locale"


def single_translate(translator, text, retries=3, delay=1.0):
    for attempt in range(retries):
        try:
            return translator.translate(text)
        except Exception as e:
            logger.warning(f"❌ Translation failed (attempt {attempt+1}): {e}")
            time.sleep(delay)
    return ""


def batch_translate(translator, texts, retries=2, delay=1.0):
    for attempt in range(retries):
        try:
            return translator.translate_batch(texts)
        except Exception as e:
            logger.warning(f"⚠️ Batch failed (attempt {attempt+1}): {e}")
            time.sleep(delay)
    return None


def process_language_dir(lang_dir: str):
    lang_path = BASE_DIR / lang_dir / "LC_MESSAGES" / "apc.po"
    if not lang_path.exists():
        return

    logger.info(f"🌐 Processing: {lang_dir}")
    po = polib.pofile(str(lang_path))
    target_lang = lang_dir.split("_")[0]
    if target_lang == "zh":
        target_lang = "zh-CN"
    translator = GoogleTranslator(source="en", target=target_lang)

    entries_to_translate = [entry for entry in po if entry.msgid and not entry.msgstr]
    success_count, fail_count = translate_entries(
        translator, entries_to_translate, lang_dir
    )

    po.save(str(lang_path))
    logger.info(f"✅ Saved: {lang_path}")
    logger.info(f"✨ Translated: {success_count}, Failed: {fail_count}")


def translate_entries(translator, entries, lang_dir):
    success_count = 0
    fail_count = 0

    for i in tqdm(range(0, len(entries), 10), desc=f"📝 Translating {lang_dir}"):
        batch = entries[i : i + 10]
        texts = [entry.msgid for entry in batch]
        translations = batch_translate(translator, texts)

        if translations and len(translations) == len(batch):
            for entry, translated in zip(batch, translations):
                entry.msgstr = translated
                success_count += 1
        else:
            for entry in batch:
                translated = single_translate(translator, entry.msgid)
                if translated:
                    entry.msgstr = translated
                    success_count += 1
                else:
                    fail_count += 1

        time.sleep(0.5)

    return success_count, fail_count


def main():
    for lang_dir in os.listdir(BASE_DIR):
        process_language_dir(lang_dir)
    logger.info("🎉 All translations complete.")


if __name__ == "__main__":
    main()
