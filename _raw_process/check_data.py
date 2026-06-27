import json
import os

categories = {
    "politik": "1_news-politik/3_politik_cnn_articles.json",
    "ekonomi": "2_news-ekonomi/3_ekonomi_cnn_articles.json",
    "teknologi": "3_news-teknologi/3_teknologi_cnn_articles.json",
    "olahraga": "4_news-olahraga/3_olahraga_cnn_articles.json",
    "hiburan": "5_news-hiburan/3_hiburan_cnn_articles.json",
}

base_dir = r"c:\yuriCode\personal_github\NLP\berita"

for cat, path in categories.items():
    full_path = os.path.join(base_dir, path)
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    text_lengths = [len(article["text"]) for article in data]
    avg_len = sum(text_lengths) / len(text_lengths)
    
    print(f"\n=== {cat.upper()} ===")
    print(f"  Total articles: {len(data)}")
    print(f"  Keys: {list(data[0].keys())}")
    print(f"  Avg text length: {avg_len:.0f} chars")
    print(f"  Min text length: {min(text_lengths)} chars")
    print(f"  Max text length: {max(text_lengths)} chars")
    
    # Count tokens roughly (words)
    word_counts = [len(article["text"].split()) for article in data]
    avg_words = sum(word_counts) / len(word_counts)
    print(f"  Avg word count: {avg_words:.0f} words")
    print(f"  Max word count: {max(word_counts)} words")
