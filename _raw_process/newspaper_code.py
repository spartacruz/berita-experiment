import newspaper
from newspaper import Article

url = "https://www.cnnindonesia.com/nasional/20260608182319-32-1366762/ruu-polri-usia-pensiun-bintara-tamtama-59-tahun-perwira-60-tahun"
article = Article(url)
article.download()
article.parse()

print(article.title)
print(article.text)
# print(article.authors)

# tempo_paper = newspaper.build(
#     "https://www.cnnindonesia.com/nasional/20260608144817-32-1366669/ruu-polri-pertahankan-syarat-minimal-sma-untuk-calon-anggota-polri"
# )

# for article in tempo_paper.articles:
#     print(article.text)
