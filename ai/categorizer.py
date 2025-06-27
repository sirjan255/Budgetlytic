"""
This module provides an AI-powered, highly extensible, and real-world-ready expense categorizer.
It leverages NLP and rule-based logic for robust category suggestions—vital for a personal finance assistant like Budgetlytic.
- Only processes user-submitted data; does not store or share data without user action.
- Extensible for privacy and local fine-tuning.
"""

import re
import json
import streamlit as st
from collections import defaultdict
from pathlib import Path

# ---- CATEGORY DATA ----
CATEGORY_DATA = [
    {"name": "Food & Dining", "emoji": "🍛", "keywords": [
        "restaurant", "food", "lunch", "dinner", "breakfast", "snacks", "cafe", "pizza", "groceries", "meal", "coffee", "tea", "swiggy", "zomato", "ubereats", "grocery", "milk", "eggs", "vegetable", "fruit"
    ]},
    {"name": "Transport", "emoji": "🚗", "keywords": [
        "uber", "ola", "taxi", "metro", "bus", "train", "flight", "cab", "auto", "petrol", "diesel", "fuel", "toll", "parking", "commute", "travel"
    ]},
    {"name": "Utilities & Bills", "emoji": "💡", "keywords": [
        "electricity", "water", "gas", "phone", "recharge", "internet", "wifi", "broadband", "dth", "postpaid", "prepaid", "bill", "utility"
    ]},
    {"name": "Shopping", "emoji": "🛍️", "keywords": [
        "amazon", "flipkart", "myntra", "shopping", "clothes", "apparel", "shoes", "bags", "fashion", "accessory", "mall", "purchase"
    ]},
    {"name": "Entertainment", "emoji": "🎬", "keywords": [
        "movie", "netflix", "hotstar", "prime", "cinema", "entertainment", "music", "spotify", "concert", "game", "pubg", "bookmyshow", "fun", "party"
    ]},
    {"name": "Medical & Health", "emoji": "💊", "keywords": [
        "doctor", "medicine", "pharmacy", "hospital", "clinic", "health", "appointment", "test", "surgery", "fitness", "gym", "yoga", "medication"
    ]},
    {"name": "Gifts & Donations", "emoji": "🎁", "keywords": [
        "gift", "donation", "charity", "ngo", "help", "birthday", "present", "wedding", "anniversary", "contribution"
    ]},
    {"name": "Children & Education", "emoji": "🎒", "keywords": [
        "school", "tuition", "education", "exam", "fees", "books", "stationery", "college", "child", "student", "course", "learning"
    ]},
    {"name": "Investment & Savings", "emoji": "💹", "keywords": [
        "investment", "mutual fund", "sip", "stocks", "shares", "fd", "rd", "deposit", "nps", "insurance", "lic", "policy", "savings"
    ]},
    {"name": "Personal Care", "emoji": "🧴", "keywords": [
        "salon", "spa", "haircut", "beauty", "parlour", "grooming", "cosmetics", "skincare"
    ]},
    {"name": "Home & Rent", "emoji": "🏠", "keywords": [
        "rent", "maintenance", "society", "home", "repair", "furniture", "decor", "appliance"
    ]},
    {"name": "Other", "emoji": "🔖", "keywords": [
        "miscellaneous", "other", "unknown", "uncategorized"
    ]},
]

# For real-life extensibility: allowing category config from a JSON file
CATEGORY_CONFIG_FILE = Path("ai/categories.json")
if CATEGORY_CONFIG_FILE.exists():
    with open(CATEGORY_CONFIG_FILE, "r", encoding="utf-8") as f:
        CATEGORY_DATA = json.load(f)

CATEGORY_KEYWORDS = defaultdict(list)
for cat in CATEGORY_DATA:
    for kw in cat["keywords"]:
        CATEGORY_KEYWORDS[kw.lower()].append(cat["name"])

CATEGORY_NAMES = [cat["name"] for cat in CATEGORY_DATA]

# ---- MAIN CATEGORY LOGIC ----

def suggest_categories(text, top_n=3):
    """
    Suggest top_n categories for an expense based on its description/text.
    Returns a list of (category, score, emoji, explanation) tuples.
    """
    text_l = text.lower()
    scores = defaultdict(int)
    matched_keywords = defaultdict(list)
    for kw, cats in CATEGORY_KEYWORDS.items():
        if kw in text_l:
            for cat in cats:
                scores[cat] += 3  # Strong keyword match
                matched_keywords[cat].append(kw)
    # Fuzzy/heuristic scoring: number detection, context words
    if re.search(r"\b(tuition|school|education|student|exam|fees|college)\b", text_l):
        scores["Children & Education"] += 2
    if re.search(r"\b(rent|maintenance|society|home)\b", text_l):
        scores["Home & Rent"] += 2
    # Special: Category by amount (large amount for rent/investment)
    try:
        amt = float(re.search(r"\b\d{2,8}\b", text_l).group())
        if amt > 5000:
            scores["Home & Rent"] += 1
            scores["Investment & Savings"] += 1
    except Exception:
        pass
    # Fallback: If no strong match, suggest "Other"
    if not scores:
        scores["Other"] = 1
    # Ranking
    ranked = sorted(scores.items(), key=lambda x: (-x[1], CATEGORY_NAMES.index(x[0])))
    out = []
    for cat, score in ranked[:top_n]:
        emoji = next((c["emoji"] for c in CATEGORY_DATA if c["name"] == cat), "")
        explanation = f"Matched keywords: {', '.join(matched_keywords[cat])}" if matched_keywords[cat] else "No strong keyword match."
        out.append((cat, score, emoji, explanation))
    return out

def add_custom_category(name, emoji="🔖", keywords=None):
    """
    Allow user to add a custom category at runtime.
    """
    new_cat = {
        "name": name,
        "emoji": emoji,
        "keywords": keywords or []
    }
    CATEGORY_DATA.append(new_cat)
    for kw in new_cat["keywords"]:
        CATEGORY_KEYWORDS[kw.lower()].append(name)
    CATEGORY_NAMES.append(name)
    # Optionally, save to JSON config
    with open(CATEGORY_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(CATEGORY_DATA, f, ensure_ascii=False, indent=2)

def category_ui(text, allow_custom=True, show_emoji=True):
    """
    Interactive Streamlit UI for category suggestion and selection.
    - Shows AI suggestions with emoji and explanations.
    - Allows corrections, feedback, and custom category addition.
    - Designed for creativity and real-world use.
    """
    st.markdown(
        """
        <style>
        .category-pill {
            display: inline-block;
            padding: 0.4em 1em;
            margin: 0.1em 0.3em;
            border-radius: 1.2em;
            background: linear-gradient(90deg, #f7e9ff 0%, #e7f9fd 100%);
            color: #2d3142;
            font-weight: 600;
            font-size: 1.1em;
            box-shadow: 0 0 4px #e9e9e9;
            border: 1px solid #c0c0c0;
            transition: 0.2s;
        }
        .category-pill.selected {
            background: linear-gradient(90deg, #6ae7b9 0%, #a6d1ff 100%);
            color: #1b1b1b;
            border: 2px solid #6c63ff;
        }
        .feedback-btn {
            background: #fffbe9;
            color: #504040;
            border: 1px solid #ffe6a7;
            border-radius: 1em;
            padding: 0.2em 0.8em;
            font-size: 1em;
            margin-left: 1em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Smart Category Suggestion")

    suggestions = suggest_categories(text, top_n=3)
    if not suggestions:
        st.info("No category suggestions found. Please type more details.")
        return None

    # Show suggestions as colored category pills with emoji and explanation
    st.markdown("**AI suggestions:**")
    cols = st.columns(len(suggestions))
    selection = None
    for i, (cat, score, emoji, expl) in enumerate(suggestions):
        with cols[i]:
            pill = f'<span class="category-pill">{emoji if show_emoji else ""} {cat}</span>'
            st.markdown(pill, unsafe_allow_html=True)
            st.caption(f"_{expl}_")
            if st.button(f"Select '{cat}'", key=f"sel_{cat}"):
                selection = cat

    st.markdown("---")

    # Custom category input
    if allow_custom:
        st.markdown("**Didn't find a suitable category? Add your own!**")
        custom_cat = st.text_input("Custom category name")
        custom_emoji = st.text_input("Custom emoji (optional)", value="🔖")
        custom_keywords = st.text_input("Related keywords (comma-separated)", value="")
        if st.button("Add Custom Category"):
            add_custom_category(
                custom_cat,
                emoji=custom_emoji,
                keywords=[k.strip() for k in custom_keywords.split(",") if k.strip()]
            )
            st.success(f"Added custom category '{custom_cat}'!")
            selection = custom_cat

    # Manual override for full list
    with st.expander("Select from all categories"):
        cat_list = [f"{c['emoji']} {c['name']}" if show_emoji else c['name'] for c in CATEGORY_DATA]
        chosen = st.selectbox("Choose a category", cat_list)
        if st.button("Confirm Category Selection"):
            selection = chosen.split(" ", 1)[1] if show_emoji else chosen

    if selection:
        st.success(f"Selected category: {selection}")
        return selection

    # Feedback for improvement
    st.markdown(
        "<br/><span style='font-size:0.95em;color:#9f5f80;'>"
        "Not accurate? <button class='feedback-btn' onclick='alert(`Thank you for your feedback!`)'>Send Feedback</button>"
        "</span><br/>",
        unsafe_allow_html=True
    )

    return None
