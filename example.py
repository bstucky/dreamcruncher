import sys
sys.path.append(r"C:\path\to\folder\containing\dreamcruncher")
from dreamcruncher import DreamCleanerGUI

# some keywords for flagging reports
keywords = ["dream","remember", "think",
            "...", "(?)"]
# some words to ignore in spellchecking step
ignorewords = ["EEG", "TV"]

# example gui use
gui = DreamCruncher(['I was dreaming that I missspelled.',
                      'Justin Bieber is lives in California, USA.',
                      'I saw Peter.', 
                       'I think I remember dreaming of a big doughnut in (?).'], keywords, ignorewords)

# get cleaned reports
gui.cleaned_reports

# get original reports
gui.original_reports

# get or save track changes
gui.tracked_changes
gui.tracked_changes.to_csv("track_changes.csv")
