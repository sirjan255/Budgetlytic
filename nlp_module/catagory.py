import re
import json
import csv
import requests
from pathlib import Path
from collections import defaultdict

import spacy
from fuzzywuzzy import fuzz

nlp = spacy.load("en_core_web_sm")
FUZZY_THRESHOLD = 85
CONCEPTNET_CACHE_FILE = "conceptnet_cache.json"

# Load or initialize ConceptNet cache
try:
    with open(CONCEPTNET_CACHE_FILE, "r", encoding="utf-8") as f:
        conceptnet_cache = json.load(f)
except:
    conceptnet_cache = {}

CATEGORY_DATA = [
    {"name": "Groceries", "priority": 1, "keywords": [
        "milk", "eggs", "bread", "rice", "atta", "flour", "salt", "sugar", "tea", "coffee",
        "biscuit", "oil", "grocery", "vegetable", "fruit", "dal", "pulses", "tofu", "curd", "paneer"
    ]},
    {"name": "Food & Dining", "priority": 2, "keywords": [
        "restaurant", "lunch", "dinner", "breakfast", "snacks", "cafe", "pizza", "meal",
        "swiggy", "zomato", "ubereats", "biryani", "noodles", "thali"
    ]},
    {"name": "Transport", "priority": 3, "keywords": [
        "uber", "ola", "taxi", "metro", "bus", "train", "flight", "cab", "auto", "commute", "parking"
    ]},
    {"name": "Utilities & Bills", "priority": 4, "keywords": [
        "electricity", "water", "gas", "phone", "recharge", "internet", "wifi", "broadband", "dth", "bill"
    ]},
    {"name": "Shopping", "priority": 5, "keywords": [
        "amazon", "flipkart", "myntra", "shopping", "purchase", "mall", "store", "shop"
    ]},
    {"name": "Clothing & Fashion", "priority": 6, "keywords": [
        "shirt", "jeans", "dress", "clothes", "tshirt", "kurti", "saree", "shoes", "fashion", "apparel"
    ]},
    {"name": "Entertainment", "priority": 7, "keywords": [
        "movie", "cinema", "netflix", "prime", "hotstar", "spotify", "fun", "bookmyshow", "theatre"
    ]},
    {"name": "Events & Subscriptions", "priority": 8, "keywords": [
        "membership", "subscription", "ticket", "event"
    ]},
    {"name": "Medical & Health", "priority": 9, "keywords": [
        "doctor", "medicine", "pharmacy", "clinic", "hospital", "gym", "fitness", "yoga", "medication"
    ]},
    {"name": "Personal Care", "priority": 10, "keywords": [
        "shampoo", "soap", "toothpaste", "skincare", "cosmetic", "makeup", "perfume", "lotion"
    ]},
    {"name": "Home Essentials", "priority": 11, "keywords": [
        "detergent", "cleaner", "handwash", "dettol", "mop", "broom", "bucket"
    ]},
    {"name": "Rent & Housing", "priority": 12, "keywords": [
        "rent", "maintenance", "society", "apartment", "housing"
    ]},
    {"name": "Investment & Savings", "priority": 13, "keywords": [
        "investment", "mutual fund", "sip", "stocks", "shares", "fd", "rd", "deposit", "nps", "lic", "premium"
    ]},
    {"name": "Education", "priority": 14, "keywords": [
        "school", "tuition", "education", "exam", "fees", "college", "book"
    ]},
    {"name": "Childcare", "priority": 15, "keywords": [
        "child", "kid", "baby", "infant"
    ]},
    {"name": "Work & Office", "priority": 16, "keywords": [
        "office", "work", "job", "project"
    ]},
    {"name": "Gifts & Donations", "priority": 17, "keywords": [
        "gift", "donation", "birthday", "wedding", "present", "ngo"
    ]},
    {"name": "Hobbies & Leisure", "priority": 18, "keywords": [
        "hobby", "craft", "art", "book", "paint", "sketch", "novel"
    ]},
    {"name": "Others", "priority": 99, "keywords": ["miscellaneous", "unknown", "other"]}
]

CATEGORY_PRIORITY = {cat["name"]: cat["priority"] for cat in CATEGORY_DATA}
CATEGORY_KEYWORDS = defaultdict(list)

for cat in CATEGORY_DATA:
    for kw in cat["keywords"]:
        CATEGORY_KEYWORDS[kw.lower()].append(cat["name"])

def get_conceptnet_isas(word):
    if word in conceptnet_cache:
        return conceptnet_cache[word]
    url = f"https://api.conceptnet.io/c/en/{word}?offset=0&limit=1000"
    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            conceptnet_cache[word] = []
            return []
        data = resp.json()
        isas = set()
        for edge in data.get("edges", []):
            if edge.get("rel", {}).get("@id") == "/r/IsA":
                end = edge.get("end", {}).get("label", "").lower()
                if end:
                    isas.add(end)
        conceptnet_cache[word] = list(isas)
        with open(CONCEPTNET_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(conceptnet_cache, f, indent=2)
        return isas
    except:
        return []

def extract_amount(text):
    match = re.findall(r"(?:₹|Rs\.?|INR)\s?(\d{2,8})", text, re.IGNORECASE)
    return float(match[-1]) if match else 0.0

def suggest_categories(text, top_n=3):
    if not text.strip():
        return [("Others", 1, "Empty line")]

    text_l = text.lower()
    doc = nlp(text_l)
    tokens = [token.lemma_ for token in doc if token.is_alpha and not token.is_stop]

    scores = defaultdict(int)
    matched_keywords = defaultdict(list)

    for token in tokens:
        token_matched = False

        for kw, cats in CATEGORY_KEYWORDS.items():
            if token == kw:
                token_matched = True
                for cat in cats:
                    scores[cat] += 3
                    matched_keywords[cat].append(f"{kw} (exact)")
            elif fuzz.ratio(token, kw) >= FUZZY_THRESHOLD:
                token_matched = True
                for cat in cats:
                    scores[cat] += 2
                    matched_keywords[cat].append(f"{token} ~ {kw} (fuzzy)")

        if not token_matched:
            isas = get_conceptnet_isas(token)
            seen_concepts = set()
            for concept in isas:
                for kw, cats in CATEGORY_KEYWORDS.items():
                    if concept == kw and (token, concept) not in seen_concepts:
                        for cat in cats:
                            scores[cat] += 1
                            matched_keywords[cat].append(f"{token} → {concept} (ConceptNet)")
                        seen_concepts.add((token, concept))

    if not scores:
        scores["Others"] += 1

    ranked = sorted(scores.items(), key=lambda x: (-x[1], CATEGORY_PRIORITY.get(x[0], 0)))

    final = []
    seen = set()
    for cat, score in ranked:
        base = cat.lower().split("&")[0].strip()
        if base in seen:
            continue
        seen.add(base)
        explanation = ", ".join(matched_keywords[cat]) if matched_keywords[cat] else "Heuristic or ConceptNet match"
        final.append((cat, score, explanation))
        if len(final) >= top_n:
            break

    return final

def process_bill_text(file_path, output_csv="categorized_expenses.csv"):
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    expense_lines = [line.strip() for line in lines if line.strip() and 'Total' not in line and 'Bill No' not in line and 'Date' not in line]

    results = []
    print(f"\nProcessing: {file_path}\n{'='*60}")
    for line in expense_lines:
        if not any(char.isdigit() for char in line):
            continue
        amount = extract_amount(line)
        suggestions = suggest_categories(line)

        if suggestions:
            cat, score, reason = suggestions[0]
            results.append({
                "Item": line,
                "Matched Category": cat,
                "Score": score,
                "Explanation": reason,
                "Amount (if found)": amount
            })

            print(f"\nItem: {line}")
            print(f" → {cat} (score: {score})")
            print(f"    Explanation: {reason}")
            print(f"    Amount: ₹{amount}")
            print("-" * 60)

    with open(output_csv, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = ["Item", "Matched Category", "Score", "Explanation", "Amount (if found)"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)

    print(f"\nResults saved to: {output_csv}\n")

bill_path = Path("sample_bill.txt")
if bill_path.exists():
    process_bill_text(bill_path)
else:
    print("File not found: sample_bill.txt")
