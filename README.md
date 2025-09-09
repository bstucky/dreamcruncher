# DreamCruncher
A python-based GUI to preprocess dream reports in a semi-automated fashion.

Features include:

1. **Find & Replace** words in reports.
2. **Anonymize Names** — replaces real names with initials or occupation if famous.
3. **Place Replacement** — identifies places and replaces them with descriptive words.
4. **Spellcheck** — highlights misspelled words and provides suggestions.
5. **Keyword Flagging** — flags reports based on keywords, for example reports containing phrases unrelated to the dream content or uncertainty.

All steps include manual control. The find & replace step is available throughout the GUI. For the first three steps checkboxes will appear so that you can apply changes only to certain flagged instances. The spellchecker allows for words to be ingnored (like EEG or TV), which would otherwise be flagged. If your keyword is "dreaming", the DreamCruncher will find the lemma "dream" and look for all realted words, like dreaming, dream, dreamt,...


## How to Run
1. Ensure you have Python 3.11 or later installed.
2. Clone or download this repository.
3. Install the required Python packages, see `requirements.txt` or run this:
```bash
pip install -r requirements.txt
4. Download the spaCy language model if not already installed:
python -m spacy download en_core_web_sm
5. Run the GUI for example with:
```bash
import sys
sys.path.append(r"C:\path\to\folder\containing\dreamcruncher")
from dreamcruncher import DreamCruncher
DreamCruncher(your_reports, your_keywords, your_spellignorewords)

