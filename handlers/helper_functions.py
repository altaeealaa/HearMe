from pydub import AudioSegment #library to concatenate audio files
import io
import string
import os
from rapidfuzz import process, fuzz

'''def merge_voice_bytes(v_en: bytes, v_ar: bytes, output_path="merged.mp3"):
    sound_en = AudioSegment.from_file(io.BytesIO(v_en), format="mp3")
    sound_ar = AudioSegment.from_file(io.BytesIO(v_ar), format="mp3")

    pause = AudioSegment.silent(duration=1000)
    combined = sound_en + pause + sound_ar

    combined.export(output_path, format="mp3")
    return output_path
'''

def normalize_text(normalized_text):
    # Convert to lowercase and strip both whitespace and punctuation
    return normalized_text.lower().strip().strip(string.punctuation)


def fuzzy_language_match(text, options, threshold=70):
    match = process.extractOne(text, options, scorer=fuzz.partial_ratio) #fuzz.partial_ratio looks for partial matches within the input text
    if match and match[1] >= threshold:
        print(f"Matched text: {match[0]}")
        return match[0]


def get_normalized_user_groups(user_groups):
    return {
        normalize_text(name): (group_id, name)
        for group_id, name in user_groups
    }