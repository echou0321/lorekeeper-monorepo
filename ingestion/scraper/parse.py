from bs4 import BeautifulSoup, Tag


def extract_sections(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', class_='mw-parser-output')
    if not content:
        return []

    for tag in content.find_all(['table', 'sup']):
        tag.decompose()
    for tag in content.find_all('div', class_='navbox'):
        tag.decompose()
    for tag in content.find_all('span', class_='mw-editsection'):
        tag.decompose()

    sections = []
    current = {'title': 'Overview', 'text': '', 'level': 2}

    for element in content.children:
        if not isinstance(element, Tag):
            continue
        if element.name in ('h2', 'h3'):
            if current['text'].strip():
                sections.append(current)
            current = {
                'title': element.get_text(strip=True).replace('[edit]', '').strip(),
                'text': '',
                'level': int(element.name[1]),
            }
        else:
            current['text'] += element.get_text(separator=' ', strip=True) + ' '

    if current['text'].strip():
        sections.append(current)

    return sections
