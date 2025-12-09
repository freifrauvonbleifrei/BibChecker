import json
import re
import unicodedata
import string
import os
import html

def load_source_patterns():
    config_path = os.path.join(os.path.dirname(__file__), "exclusions.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("Warning: Could not load exclusions.json:", e)
        return {}
exclusions = load_source_patterns()

def remove_special_chars(s):
    s = html.unescape(s) 
    s = re.sub(r'<mml:[^>]+>', '', s)
    s = re.sub(r'</mml:[^>]+>', '', s)
    s = re.sub(r'<[^>]+>', '', s)    
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'[\u2010-\u2015\u2212]', '-', s)    
    return s

#Remove zero space and normalize to unicode
#Remove newlines, with no space if `-\n` and space if just '\n'
def normalize_entry(text):
    text = remove_special_chars(text)
    text = re.sub(r'([A-Za-z])-\s+([A-Za-z])', r'\1\2', text)
    text = re.sub(r'-(\w)\s+([a-z])', r'-\1\2', text)
    text = re.sub(r'\b([B-HJ-Z])\s+([a-z]{2,})\b', r'\1\2', text)
    text = text.replace('-\n', '')
    text = text.replace('\n', ' ')
    return text
    
def format_for_url(text):
    text = text.lower()
    text = text.replace('\n', '').replace(' ', '')
    return text


def normalize_authors(author_block):
    cleaned = remove_special_chars(author_block).replace('  ', ' ')
    cleaned = re.sub(r'\b([A-Z][a-z]+)\s+([a-z])\b', r'\1\2', cleaned)
    return cleaned

def normalize_title(title):
    title = normalize_entry(title)
    title = re.sub(r'\b([A-Za-z0-9]+)\s*-\s*([A-Za-z0-9]+)\b', r'\1 \2', title)
    title = re.sub(r'[^A-Za-z0-9 ]+', '', title)
    title = re.sub(r'\s+', ' ', title)
    return title.lower().strip() 

def normalize_hyphen_title(title):
    title = title.replace('-\n', ' ')
    title = normalize_title(title)
    return title


