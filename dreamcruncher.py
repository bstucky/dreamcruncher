# -*- coding: utf-8 -*-
"""
Created on Fri Aug 22 14:01:41 2025

@author: Benjamin Stucky
"""
import tkinter as tk
from tkinter import scrolledtext
import tkinter.font as tkfont
import copy
import spacy # additionally python -m spacy download en_core_web_sm
from spellchecker import SpellChecker # pip install pyspellchecker

import pandas as pd

import string

import re

import platform

import requests
import subprocess, sys

# gui.cleaned_reports output reports
class DreamCruncher:
    def __init__(self, reports, keywords, exceptions=None):
        
        try:
            self.nlp = spacy.load("en_core_web_lg")
        except OSError:
            print("spaCy model en_core_web_lg not installed, downloading")
            subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_lg"])
            self.nlp = spacy.load("en_core_web_lg")

        self.spell = SpellChecker()
        
        if hasattr(reports, "tolist"):  # e.g. a Pandas Series
            reports = reports.tolist()
    
    
        self.original_reports = list(reports)
        self.cleaned_reports = copy.deepcopy(reports)
        self.keywords = {
            (self.nlp(kw)[0].lemma_.lower() if kw.isalpha() else kw)
            for kw in keywords
            if kw
        }
        self.exceptions = {w.lower() for w in (exceptions or [])}
        
        
        # track changes
        self.changes = {i: [] for i in range(len(self.cleaned_reports))}
    
        # State variables
        self.step = 0  # Step 0: Find/Replace
        self.spellcheck_indices = []
        self.current_index = 0
        self.flagged_indices = []
        self.replace_map = {}
        self.match_vars = []  # store (report_index, kw, tk.BooleanVar)
    
        # --- GUI setup ---
        self.root = tk.Tk()
        self.root.title("Dream Reports Cleaner")
        
        # window size
        system = platform.system()
        if system == "Windows":
            self.root.state("zoomed")  # maximize like native Windows
        elif system == "Linux":
            self.root.wm_attributes("-zoomed", True)  # maximize in many Linux WMs
        else:  # macOS fallback
            self.root.attributes("-fullscreen", True)
            self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))

        # Title initialization
        title_font = tkfont.Font(family="Helvetica", size=18, weight="bold")
        self.label = tk.Label(self.root, text="Find & Replace words", font=title_font)
        self.label.pack(pady=5)
    
        # --- Step 0 input fields ---
        input_frame = tk.Frame(self.root)
        input_frame.pack(pady=5)
    
        tk.Label(input_frame, text="Find:").pack(side=tk.LEFT)
        self.find_entry = tk.Entry(input_frame, width=15)
        self.find_entry.pack(side=tk.LEFT, padx=2)
    
        find_btn = tk.Button(input_frame, text="Find", command=self.find_word_step0)
        find_btn.pack(side=tk.LEFT, padx=2)
    
        tk.Label(input_frame, text="Replace with:").pack(side=tk.LEFT)
        self.replace_entry = tk.Entry(input_frame, width=15)
        self.replace_entry.pack(side=tk.LEFT, padx=2)
    
        replace_btn = tk.Button(input_frame, text="Replace", command=self.replace_word_step0)
        replace_btn.pack(side=tk.LEFT, padx=2)
    
        # --- Select All / Select None buttons ---
        sel_frame = tk.Frame(self.root)
        sel_frame.pack(pady=5)
        tk.Button(sel_frame, text="Select All", command=self.select_all_current).pack(side=tk.LEFT, padx=2)
        tk.Button(sel_frame, text="Select None", command=self.deselect_all_current).pack(side=tk.LEFT, padx=2)


        # --- Step 0: Scrollable checkbox frame ---
        container = tk.Frame(self.root)
        container.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
    
        canvas = tk.Canvas(container, height=120)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.context_area_frame = tk.Frame(canvas)
    
        self.context_area_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
    
        canvas.create_window((0, 0), window=self.context_area_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
    
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        
        # apply name replacement button position
        if not hasattr(self, "apply_names_btn"):
            self.apply_names_btn = tk.Button(
                self.root, text="Apply Name Replacements", command=self.apply_name_replacements
            )
    
        # Step navigation buttons
        self.proceed_frame = tk.Frame(self.root)
        self.proceed_frame.pack(pady=5)  # pack the frame itself
        
        self.proceed_names_btn = tk.Button(self.proceed_frame, text="Proceed to Names", command=self.start_name_step)
        self.proceed_names_btn.pack(side=tk.LEFT, padx=5)
        
        self.proceed_names_btn = tk.Button(self.proceed_frame, text="Proceed to Places", command=self.start_place_step)
        self.proceed_names_btn.pack(side=tk.LEFT, padx=5)
        
        self.proceed_btn = tk.Button(self.proceed_frame, text="Proceed to Spellcheck", command=self.start_spellcheck)
        self.proceed_btn.pack(side=tk.LEFT, padx=5)
        
        self.proceed_keywords_btn = tk.Button(self.proceed_frame, text="Proceed to Keywords", command=self.start_keyword_step)
        self.proceed_keywords_btn.pack(side=tk.LEFT, padx=5)
    
        # --- Step 1: Spellcheck panels (side by side, hidden initially) ---
        self.pane_frame = tk.Frame(self.root)
        self.pane_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
        # Original text panel
        self.text_area = scrolledtext.ScrolledText(self.pane_frame, width=50, height=15)
        self.text_area.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        self.text_area.pack_forget()  # hide initially
    
        # Suggested correction panel
        self.suggestion_area = scrolledtext.ScrolledText(
            self.pane_frame, width=50, height=15
        )
        self.suggestion_area.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        self.suggestion_area.pack_forget()  # hide initially
    
        # Accept Suggestions button
        self.accept_btn = tk.Button(self.root, text="Accept Suggestions", command=self.accept_suggestions)
        self.accept_btn.pack(pady=2)
        self.accept_btn.pack_forget()  # hide initially
    
        # Navigation buttons (used for spellcheck and keywords)
        nav_frame = tk.Frame(self.root)
        nav_frame.pack()
        self.prev_btn = tk.Button(nav_frame, text="Previous", command=self.prev_report)
        self.next_btn = tk.Button(nav_frame, text="Next", command=self.next_report)
        self.save_exit_btn = tk.Button(nav_frame, text="Save & Exit", command=self.save_and_exit)
        self.save_exit_btn.pack(side=tk.LEFT, padx=5)  # pack immediately
        
        
        # Load first report for Step 0 preview (empty until Find is used)
        if self.cleaned_reports:
            pass  # matches appear only after user searches
            
        
        # Bind the close event to your save handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
        # Start mainloop
        self.root.mainloop()
        
        
        
    # select and deselect buttons
    def select_all_current(self):
        if self.step == 0 and hasattr(self, "match_vars"):
            for m in self.match_vars:
                m[2].set(True)  # Step 0: var is at index 2
        elif self.step == 1 and hasattr(self, "name_vars"):
            for m in self.name_vars:
                m["var"].set(True)
    
    def deselect_all_current(self):
        if self.step == 0 and hasattr(self, "match_vars"):
            for m in self.match_vars:
                m[2].set(False)
        elif self.step == 1 and hasattr(self, "name_vars"):
            for m in self.name_vars:
                m["var"].set(False)



    # ---------- Spellcheck ----------
    def get_spellcheck_indices(self):
        flagged = []
        for i, report in enumerate(self.cleaned_reports):
            words = report.split()
            misspelled = []
            for w in words:
                clean_w = w.strip(string.punctuation)  # remove leading/trailing punctuation
                if clean_w and clean_w.isalpha() and clean_w.lower() not in self.spell and clean_w.lower() not in self.exceptions:
                    misspelled.append(w)
            if misspelled:
                flagged.append(i)
        return flagged

    # ---------- helper: lightweight normalization ----------
    @staticmethod
    def normalize_word(word):
        w = word.lower()
        if w.endswith("ing") and len(w) > 4:
            return w[:-3]
        if w.endswith("ed") and len(w) > 3:
            return w[:-2]
        if w.endswith("s") and len(w) > 3:
            return w[:-1]
        return w
    
    # ---------- flagging reports ----------
    def get_flagged_indices(self):
        flagged = []
        for i, report in enumerate(self.cleaned_reports):
            doc = self.nlp(report)
            for token in doc:
                lemma = token.lemma_.lower()
                lemma = self.normalize_word(lemma)  # fallback
                if lemma in self.keywords and lemma not in self.exceptions:
                    flagged.append(i)
                    break
        return flagged

    # ---------- Loading ----------
    def load_report(self):
        if self.step == 3:
            # Spellcheck step
            idx = self.spellcheck_indices[self.current_index]
            self.label.config(
                text=f"Correct spelling mistakes ({self.current_index + 1}/{len(self.spellcheck_indices)})"
            )
        elif self.step == 4:
            # Keyword step
            idx = self.flagged_indices[self.current_index]
            self.label.config(
                text=f"Remove unrelated phrases ({self.current_index + 1}/{len(self.flagged_indices)})"
            )
        else:
            # No text panel content for Step 0/1 (Find/Replace or Names list view)
            return
    
        # Original report
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, self.cleaned_reports[idx])
    
        if self.step == 3:
            self.highlight_misspelled_words(self.cleaned_reports[idx])
            self.populate_suggestions(self.cleaned_reports[idx])
        elif self.step == 4:
            self.highlight_keywords(self.cleaned_reports[idx])

        
            
    # ---------- Highlight misspelled words ----------
    def highlight_misspelled_words(self, text):
        self.text_area.tag_remove("misspelled", "1.0", tk.END)
    
        words = text.split()
        start_index = "1.0"
    
        for word in words:
            clean_w = word.strip(string.punctuation)
    
            idx_start = self.text_area.search(word, start_index, stopindex=tk.END)
            if not idx_start:
                continue
            idx_end = f"{idx_start}+{len(word)}c"
    
            if clean_w and clean_w.isalpha() and clean_w.lower() not in self.spell and clean_w.lower() not in self.exceptions:
                self.text_area.tag_add("misspelled", idx_start, idx_end)
    
            start_index = idx_end
    
        self.text_area.tag_config("misspelled", foreground="red")

    # ---------- Saving ----------
    def save_current(self):
        if self.step == 3:
            idx = self.spellcheck_indices[self.current_index]
        elif self.step == 4:
            idx = self.flagged_indices[self.current_index]
        else:
            return  # nothing to save for Step 0/1
    
        old_text = self.cleaned_reports[idx]
        new_text = self.text_area.get("1.0", tk.END).strip()
        
        # Only track if there’s a real change
        if old_text != new_text:
            self.changes[idx].append((0, len(new_text), old_text, new_text, "keyword"))
        
        self.cleaned_reports[idx] = new_text

        
        
    # ---------- Save & Exit ----------
    def save_and_exit(self):
        self.save_current()
        self.tracked_changes = self.changes_to_dataframe(
            self.original_reports, 
            self.cleaned_reports,
            self.changes
        )
        self.root.destroy()
    
    @staticmethod
    def changes_to_dataframe(original_reports, cleaned_reports, changes, context_window=10):
        rows = []
        
        for i, report_changes in changes.items():
            original = original_reports[i]
            cleaned = cleaned_reports[i]
            
            for change in report_changes:
                start, end, old_text, new_text, change_type = change
                
                # get context from original report
                start_ctx = max(0, start - context_window)
                end_ctx = min(len(original), end + context_window)
                context = original[start_ctx:end_ctx].replace("\n", " ")
                
                rows.append({
                    "report_idx": i,
                    "original_report": original,
                    "cleaned_report": cleaned,
                    "change_type": change_type,
                    "old_text": old_text,
                    "new_text": new_text,
                    "context": context
                })
        
        df = pd.DataFrame(rows)
        return df
        
    def on_close(self):
        self.save_current()  # save the currently visible report
        
        self.tracked_changes = self.changes_to_dataframe(self.original_reports, 
                                                       self.cleaned_reports,
                                                       self.changes)
    
        # Destroy the GUI
        self.root.destroy()
        
    def finalize_and_close(self):
        self.save_current()
        self.tracked_changes = self.changes_to_dataframe(
            self.original_reports,
            self.cleaned_reports,
            self.changes
        )
        self.root.destroy()



    # ---------- Navigation ----------
    def next_report(self):
        self.save_current()
        if self.step == 3:
            if self.current_index < len(self.spellcheck_indices) - 1:
                self.current_index += 1
                self.load_report()
            else:
                # finish spellcheck → keywords
                self.start_keyword_step()
        elif self.step == 4:
            if self.current_index < len(self.flagged_indices) - 1:
                self.current_index += 1
                self.load_report()
            else:
                self.finalize_and_close()
    
    def prev_report(self):
        self.save_current()
        if self.step in (3, 4) and self.current_index > 0:
            self.current_index -= 1
            self.load_report()


    # ---------- Start Keyword Step ----------
    def start_keyword_step(self):
        # add next and prev buttons
        self.prev_btn.pack(side=tk.LEFT, padx=5, before=self.save_exit_btn)
        self.next_btn.pack(side=tk.LEFT, padx=5, before=self.save_exit_btn)
        
        # hide name apply button
        if hasattr(self, "apply_names_btn"):
            self.apply_names_btn.pack_forget()
        # remove apply places buttons
        if hasattr(self, "apply_places_btn") and self.apply_places_btn.winfo_exists():
            self.apply_places_btn.pack_forget()
        
        # hide name checkboxes / context
        for widget in self.context_area_frame.winfo_children():
            widget.destroy()
        self.step = 4
        self.flagged_indices = self.get_flagged_indices()
        self.current_index = 0
        self.label.config(text="Remove unrelated phrases")
        self.root.title("Dream Reports Cleaner - Keyword Cleaning Step")
    
        # One-line tweak: make sure the text area is visible
        self.text_area.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
    
        # Hide spellcheck widgets
        self.suggestion_area.pack_forget()
        self.accept_btn.pack_forget()
    
        if self.flagged_indices:
            self.load_report()
        else:
            self.finalize_and_close()

            
    # ---------- highlighting keywords ----------
    def highlight_keywords(self, text):
        self.text_area.tag_remove("keyword", "1.0", tk.END)
        doc = self.nlp(text)
    
        # --- highlight normal words using spaCy + normalization ---
        for token in doc:
            lemma = token.lemma_.lower()
            lemma = self.normalize_word(lemma)
            if lemma in self.keywords and lemma not in self.exceptions:
                start_idx = "1.0"
                while True:
                    start_idx = self.text_area.search(token.text, start_idx, stopindex=tk.END)
                    if not start_idx:
                        break
                    end_idx = f"{start_idx}+{len(token.text)}c"
                    self.text_area.tag_add("keyword", start_idx, end_idx)
                    start_idx = end_idx
    
        # --- highlight special/non-alphabetic keywords ---
        for kw in self.keywords:
            if kw.isalpha() or not kw:  # skip normal words and empty strings
                continue
            start_idx = "1.0"
            while True:
                start_idx = self.text_area.search(kw, start_idx, stopindex=tk.END)
                if not start_idx:
                    break
                end_idx = f"{start_idx}+{len(kw)}c"
                self.text_area.tag_add("keyword", start_idx, end_idx)
                start_idx = end_idx
    
        self.text_area.tag_config("keyword", foreground="orange")

    
    def get_replace_contexts(self, report, targets, window=5):
        doc = self.nlp(report)
        contexts = []
    
        for ent in doc.ents:
            if ent.label_ == "PERSON" and ent.text in targets:
                start_token = max(ent.start - window, 0)
                end_token = min(ent.end + window, len(doc))
                context_tokens = [t.text for t in doc[start_token:ent.start]]  # tokens before entity
                context_tokens.append(f"[{ent.text}]")                          # entity itself
                context_tokens += [t.text for t in doc[ent.end:end_token]]      # tokens after entity
                contexts.append((ent.text, " ".join(context_tokens)))
    
        # fallback
        if not contexts:
            for t in targets:
                contexts.append((t, f"[{t}]"))
        return contexts



    def get_word_contexts(self, report, targets, window=5):
        doc = self.nlp(report)
        contexts = []
        lowered_targets = [t.lower() for t in targets]
    
        for token in doc:
            token_text = token.text.strip(string.punctuation)
            if not token_text:
                continue
            if token_text.lower() in lowered_targets:
                idx = token.i
    
                # move left until we've collected `window` words (non-empty after stripping punctuation)
                left = idx
                words = 0
                while left > 0 and words < window:
                    left -= 1
                    if doc[left].text.strip(string.punctuation):
                        words += 1
    
                # move right until we've collected `window` words
                right = idx
                words = 0
                while right < len(doc) - 1 and words < window:
                    right += 1
                    if doc[right].text.strip(string.punctuation):
                        words += 1
    
                # build context tokens and char offsets
                context_tokens = [t.text for t in doc[left:idx]]
                context_tokens.append(f"[{token.text}]")
                context_tokens += [t.text for t in doc[idx + 1 : right + 1]]
    
                start_char = token.idx
                end_char = token.idx + len(token.text)
                contexts.append((token.text, " ".join(context_tokens), start_char, end_char))
    
        return contexts



    # find words
    def find_word_step0(self):
        word = self.find_entry.get().strip()
        if not word:
            return
    
        # clear previous results
        for widget in self.context_area_frame.winfo_children():
            widget.destroy()
    
        self.match_vars = []  # store checkboxes for matches; structure: (report_idx, matched_text, var, start_char, end_char)
    
        found_any = False
        for i, report in enumerate(self.cleaned_reports):
            ctxs = self.get_word_contexts(report, [word], window=5)
            if ctxs:
                found_any = True
                tk.Label(self.context_area_frame, text=f"Report {i+1}:", fg="blue").pack(anchor="w")
    
                for matched_text, ctx, start_char, end_char in ctxs:
                    var = tk.BooleanVar(value=True)  # default: selected
                    chk = tk.Checkbutton(
                        self.context_area_frame,
                        text=f"...{ctx}...",
                        variable=var,
                        anchor="w",
                        justify="left"
                    )
                    chk.pack(anchor="w", fill="x")
                    # store offsets so replacement is precise
                    self.match_vars.append((i, matched_text, var, start_char, end_char))
    
        if not found_any:
            tk.Label(
                self.context_area_frame,
                text=f"No occurrences of '{word}' found.",
                fg="red"
            ).pack(anchor="w")



    def replace_word_step0(self):
        find_word = self.find_entry.get().strip()
        replace_word = self.replace_entry.get().strip()
        if not find_word:
            return
    
        # collect replacements per report: (start, end, repl)
        replacements_by_report = {}
        for item in self.match_vars:
            # item is (report_idx, matched_text, var, start_char, end_char)
            report_idx, _, var, start_char, end_char = item
            if var.get():
                replacements_by_report.setdefault(report_idx, []).append((start_char, end_char, replace_word))
    
        # apply each report's replacements in reverse order (by start offset)
        for report_idx, reps in replacements_by_report.items():
            text = self.cleaned_reports[report_idx]
            reps_sorted = sorted(reps, key=lambda x: x[0], reverse=True)
            for start, end, repl in reps_sorted:
                old_text = text[start:end]
                text = text[:start] + repl + text[end:]
                
                # Track change
                self.changes[report_idx].append((start, start+len(repl), old_text, repl, "replace"))
                
            self.cleaned_reports[report_idx] = text
    
        # Refresh the checkboxes / contexts to reflect new text
        self.find_word_step0()



    
    def start_spellcheck(self):
        
        # add next and prev buttons
        self.prev_btn.pack(side=tk.LEFT, padx=5, before=self.save_exit_btn)
        self.next_btn.pack(side=tk.LEFT, padx=5, before=self.save_exit_btn)
        
        
        # hide name apply button
        if hasattr(self, "apply_names_btn"):
            self.apply_names_btn.pack_forget()
            
        # remove apply places buttons
        if hasattr(self, "apply_places_btn") and self.apply_places_btn.winfo_exists():
            self.apply_places_btn.pack_forget()
        
        # hide name checkboxes / context
        for widget in self.context_area_frame.winfo_children():
            widget.destroy()
        self.step = 3
        self.label.config(text="Correct spelling mistakes")
        self.spellcheck_indices = self.get_spellcheck_indices()
        self.current_index = 0
    
        # Hide Step 0 widgets
        # self.context_area.pack_forget()
        # self.find_entry.pack_forget()
        # self.replace_entry.pack_forget()
        # self.proceed_btn.pack_forget()
    
        # Show spellcheck panels
        self.text_area.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        self.suggestion_area.pack(side=tk.LEFT, padx=5, fill=tk.BOTH, expand=True)
        self.accept_btn.pack(pady=2)
    
        if self.spellcheck_indices:
            self.load_report()
        else:
            self.start_keyword_step()
            



            
    def populate_suggestions(self, text): 
        self.suggestion_area.delete("1.0", tk.END)
        self.suggestion_area.tag_config("changed", foreground="green")
    
        # Split into words & newlines, so we keep full structure
        tokens = re.findall(r'\S+|\n', text)
    
        for tok in tokens:
            if tok == "\n":
                self.suggestion_area.insert(tk.END, "\n")
                continue
    
            clean_w = tok.strip(string.punctuation)
            if clean_w and clean_w.isalpha() and clean_w.lower() not in self.exceptions:
                if clean_w.lower() not in self.spell:
                    suggestion = self.spell.correction(clean_w)
                    if not suggestion:  # <-- no suggestion found
                        final_word = tok
                    else:
                        prefix = tok[:len(tok) - len(tok.lstrip(string.punctuation))]
                        suffix = tok[len(tok.rstrip(string.punctuation)):]
                        final_word = prefix + suggestion + suffix
                else:
                    final_word = tok
            else:
                final_word = tok
    
            # Insert word
            start_idx = self.suggestion_area.index("insert")
            self.suggestion_area.insert(tk.END, final_word + " ")
            end_idx = self.suggestion_area.index("insert")
    
            # Highlight if changed
            if final_word != tok:
                self.suggestion_area.tag_add("changed", start_idx, f"{end_idx} -1c")

        
    def accept_suggestions(self):
        suggested_text = self.suggestion_area.get("1.0", tk.END).strip()
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert(tk.END, suggested_text)
        
        idx = self.spellcheck_indices[self.current_index]
        old_text = self.cleaned_reports[idx]
        new_text = self.suggestion_area.get("1.0", tk.END).strip()
        
        self.cleaned_reports[idx] = new_text
        
        # Track the change for the full report
        self.changes[idx].append((0, len(new_text), old_text, new_text, "spellcheck"))
        

    def get_name_suggestion(self, name):
        search_url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={name}&language=en&limit=1&format=json"
        headers = {"User-Agent": "Python"}
    
        occupation_keywords = {
            # Arts & Entertainment
            "actor", "actress", "singer", "musician", "songwriter", "composer",
            "dancer", "director", "producer", "painter", "artist", "poet",
            "writer", "author", "novelist", "playwright", "comedian", "performer",
            "entertainer", "cartoonist", "illustrator", "editor",
            
            # Media & Broadcasting
            "host", "presenter", "broadcaster", "journalist", "anchor",
            "reporter", "talk show host",
            
            # Academia & Philosophy
            "philosopher", "scientist", "physicist", "chemist", "mathematician",
            "biologist", "historian", "professor", "researcher", "academic",
            "scholar",
            
            # Politics & Leadership
            "president", "prime minister", "chancellor", "king", "queen",
            "emperor", "politician", "diplomat", "senator", "mayor", "governor",
            
            # Sports
            "athlete", "footballer", "basketball player", "soccer player",
            "swimmer", "runner", "coach", "manager", "olympian",
            
            # Business & Miscellaneous Famous Roles
            "entrepreneur", "inventor", "activist", "philanthropist", "chef",
            "designer", "architect", "lawyer", "judge"
        }
    
        try:
            response = requests.get(search_url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
    
            # No match → fallback to first initial
            if not data.get("search"):
                return name[0] + "."
    
            description = data["search"][0].get("description", "").lower()
    
            # Generic names or places → first initial
            if "given name" in description or "family name" in description:
                return name[0] + "."
    
            # Remove parentheses and commas
            desc_clean = description.split("(")[0].split(",")[0]
            doc = self.nlp(desc_clean)
    
            # --- Extract consecutive nouns as phrases ---
            phrases = []
            current_phrase = []
            for token in doc:
                if token.pos_ == "NOUN":
                    current_phrase.append(token.text.lower())
                else:
                    if current_phrase:
                        phrases.append(" ".join(current_phrase))
                        current_phrase = []
            if current_phrase:
                phrases.append(" ".join(current_phrase))
    
            # --- Pick the first phrase that contains an occupation keyword ---
            for phrase in phrases:
                if any(kw in phrase for kw in occupation_keywords):
                    return phrase
    
            # Fallback → first initial
            return name[0] + "."
    
        except (requests.RequestException, ValueError):
            return name[0] + "."


        
    
    def get_name_matches(self):
        matches = []
    
        for i, report in enumerate(self.cleaned_reports):
            doc = self.nlp(report)
            for ent in doc.ents:
                if ent.label_ == "PERSON":
                    name_text = ent.text.strip()
                    suggestion = self.get_name_suggestion(name_text)
    
                    matches.append({
                        "report_idx": i,
                        "original": name_text,
                        "suggestion": suggestion
                    })
        return matches






    # name method
    def start_name_step(self):
        self.step = 1
        self.root.title("Dream Reports Cleaner - Name Anonymization Step")
        self.label.config(text="Flag and anonymize names")
        
        # remove previous and next buttons
        self.prev_btn.pack_forget()
        self.next_btn.pack_forget()
        # remove widgets
        self.text_area.pack_forget()
        self.suggestion_area.pack_forget()
        self.accept_btn.pack_forget()
        # remove apply places buttons
        if hasattr(self, "apply_places_btn") and self.apply_places_btn.winfo_exists():
            self.apply_places_btn.destroy()
    
        # Clear any previous Name step widgets
        if hasattr(self, "name_vars_widgets"):
            self.clear_name_widgets()
        self.name_vars_widgets = []
    
        # Create or show Apply Names button above the context area
        self.apply_names_btn = tk.Button(
            self.root, text="Apply Name Replacements", command=self.apply_name_replacements
        )
        self.apply_names_btn.pack_forget()
        self.apply_names_btn.pack(pady=5, before=self.proceed_frame)
    
        # Clear context area
        for widget in self.context_area_frame.winfo_children():
            widget.destroy()
    
        # Get all name matches
        self.name_matches = self.get_name_matches()
    
        if not self.name_matches:
            # No names found → skip to spellcheck
            self.apply_names_btn.pack_forget()
            self.start_place_step()
            return
    
        # Build GUI for each name match
        self.name_vars = []  # (report_idx, original, entry, var)
        for match in self.name_matches:
            row = tk.Frame(self.context_area_frame)
            row.pack(fill="x", pady=2)
    
            # Checkbox
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(row, variable=var)
            chk.pack(side="left")
    
            # Context preview (±5 words)
            ctxs = self.get_replace_contexts(
                self.cleaned_reports[match["report_idx"]],
                [match["original"]],
                window=5
            )
            context_text = " ... ".join(ctx for _, ctx in ctxs) if ctxs else match["original"]
            lbl = tk.Label(row, text=f"...{context_text}...")
            lbl.pack(side="left", padx=5)
    
            # Suggestion entry
            entry = tk.Entry(row, width=20)
            
            # apply article immediately
            entry.insert(0, match["suggestion"])
            entry.pack(side="left", padx=5)
            
            # Save for applying replacements
            self.name_vars.append({
                "report_idx": match["report_idx"],
                "original": match["original"],
                "entry": entry,
                "var": var,
                "row": row  # keep reference to GUI row
            })



    
    # apply name replacements
    def apply_name_replacements(self):
        if not hasattr(self, "name_vars"):
            self.start_start_place_step()
            return
    
        still_active = []
    
        for match in self.name_vars:
            if not match["var"].get():  # unchecked → keep in GUI
                still_active.append(match)
                continue
    
            report_idx = match["report_idx"]
            report_text = self.cleaned_reports[report_idx]
    
            doc = self.nlp(report_text)
            replacements = []
    
            # Find entity match in the report
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                if ent.text != match["original"]:
                    continue
    
                role = match["entry"].get().strip()
                dep = ent.root.dep_
    
                if len(role) == 2 and role[1] == ".":  # initials like "J."
                    repl = role
                else:
                    # Determine if we should capitalize the article
                    capitalize_article = False
                    pre_text = report_text[:ent.start_char].rstrip()
                    if not pre_text or pre_text[-1] in ".!?":
                        capitalize_article = True
    
                    repl = self.add_article(role, capitalize=capitalize_article, definite=False)
    
                replacements.append((ent.start_char, ent.end_char, repl))
    
            # Apply replacements from end → start to not break offsets
            replacements.sort(reverse=True)
            for start, end, repl in replacements:
                old_text = report_text[start:end]
                report_text = report_text[:start] + repl + report_text[end:]
                
                # Track change
                self.changes[report_idx].append((start, start+len(repl), old_text, repl, "name"))
    
            self.cleaned_reports[report_idx] = report_text
    
            # Remove the row from GUI
            match["row"].destroy()
    
        # Keep only unreplaced matches
        self.name_vars = [m for m in still_active if m["var"].get() is False]
    
        # If no more names left, hide button and proceed
        if not self.name_vars:
            self.apply_names_btn.pack_forget()
            self.start_place_step()




    
    @staticmethod
    def add_article(word, capitalize=False, definite=False):
        """Add 'a/an' or 'The' to a word depending on flags."""
        if not word:
            return word
        if definite:
            word = f"The {word}"
        else:
            if word[0].lower() in "aeiou":
                word = f"an {word}"
            else:
                word = f"a {word}"
        if capitalize:
            word = word[0].upper() + word[1:]
        return word



        
    def clear_name_widgets(self):
        for widget in getattr(self, "name_vars_widgets", []):
            widget.destroy()
        self.name_vars_widgets = []
        
    # match places
    def get_place_matches(self):
        matches = []
        for i, report in enumerate(self.cleaned_reports):
            doc = self.nlp(report)
            for ent in doc.ents:
                if ent.label_ in {"GPE", "LOC", "FAC"}:
                    suggestion = self.get_place_suggestion(ent.text)
                    matches.append({
                        "report_idx": i,
                        "original": ent.text,
                        "suggestion": suggestion
                    })
        return matches

    @staticmethod
    def get_place_suggestion(place_name):
        """
        Look up a place on Wikidata and suggest a type like 'city', 'river', 'country', 'monument'.
        Fallback: 'place'
        """
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": place_name,
            "language": "en",
            "limit": 1,
            "format": "json"
        }
        headers = {"User-Agent": "Python"}
        
        try:
            response = requests.get(search_url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("search"):
                return "place"
            
            description = data["search"][0].get("description", "").lower()

            place_keywords = {
                "city": ["city", "cities", "megacity", "megacities", "metropolis", "urban area", "municipality"],
                "town": ["town", "towns", "village", "villages"],
                "country": ["country", "nation"],
                "state": ["state", "states", "province", "provinces", "canton", "cantons", "governorate"],
                "river": ["river", "rivers", "stream", "creek"],
                "lake": ["lake", "lakes", "reservoir", "pond"],
                "ocean": ["sea", "seas", "ocean", "oceans", "coast", "costal", "gulf", "bay"],
                "landmark": ["monument", "building", "structure",
                             "landmark", "tower", "statue", "temple", 
                             "cathedral", "church", "mosque", "castle", "fort"],
            }
        
            for place_type, keywords in place_keywords.items():
                if any(keyword in description for keyword in keywords):
                    return place_type
        
            return "place"
            
        except (requests.RequestException, ValueError):
            return "place"

    
    def start_place_step(self):
        self.step = 2  # Step number for Places
        self.root.title("Place Anonymization")
        self.label.config(text="Flag and anonymize places")
        
        # Remove any Apply Names button
        if hasattr(self, "apply_names_btn") and self.apply_names_btn.winfo_exists():
            self.apply_names_btn.destroy()
        
        # Clear previous context widgets
        for widget in self.context_area_frame.winfo_children():
            widget.destroy()
        
        # Get place matches
        self.place_matches = self.get_place_matches()
        
        if not self.place_matches:
            # Skip to spellcheck if nothing found
            self.start_spellcheck()
            return
        
        # Create Apply Places button
        self.apply_places_btn = tk.Button(
            self.root, text="Apply Place Replacements", command=self.apply_place_replacements
        )
        self.apply_places_btn.pack(pady=5, before=self.proceed_frame)
        
        # Build GUI for each match
        self.place_vars = []
        for match in self.place_matches:
            row = tk.Frame(self.context_area_frame)
            row.pack(fill="x", pady=2)
            
            # Checkbox
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(row, variable=var)
            chk.pack(side="left")
            
            # Context preview ±5 words
            ctxs = self.get_place_contexts(
                self.cleaned_reports[match["report_idx"]],
                [match["original"]],
                window=5
            )
            context_text = " ... ".join(ctx for _, ctx in ctxs) if ctxs else match["original"]
            lbl = tk.Label(row, text=f"...{context_text}...")
            lbl.pack(side="left", padx=5)
            
            # Suggestion entry
            entry = tk.Entry(row, width=20)
            entry.insert(0, match["suggestion"])
            entry.pack(side="left", padx=5)
            
            self.place_vars.append({
                "report_idx": match["report_idx"],
                "original": match["original"],
                "entry": entry,
                "var": var,
                "row": row
            })

            
    def apply_place_replacements(self):
        if not hasattr(self, "place_vars"):
            self.start_spellcheck()
            return
        
        still_active = []
        
        for match in self.place_vars:
            if not match["var"].get():
                still_active.append(match)
                continue
            
            report_idx = match["report_idx"]
            text = self.cleaned_reports[report_idx]
            doc = self.nlp(text)
            replacements = []
            
            # Find matching entity in doc
            for ent in doc.ents:
                if ent.label_ not in {"GPE", "LOC", "FAC"}:
                    continue
                if ent.text != match["original"]:
                    continue
                repl = self.add_article(match["entry"].get().strip(), capitalize=False)
                replacements.append((ent.start_char, ent.end_char, repl))
            
            # Apply replacements end → start
            replacements.sort(reverse=True)
            for start, end, repl in replacements:
                old_text = text[start:end]
                text = text[:start] + repl + text[end:]
                self.changes[report_idx].append((start, start+len(repl), old_text, repl, "place"))
            
            self.cleaned_reports[report_idx] = text
            match["row"].destroy()
        
        # Keep only unchecked
        self.place_vars = [m for m in still_active if not m["var"].get()]
        
        if not self.place_vars:
            self.apply_places_btn.destroy()
            self.start_spellcheck()
            
    def get_place_contexts(self, report, targets, window=5):
        doc = self.nlp(report)
        contexts = []
    
        for ent in doc.ents:
            if ent.text in targets:
                start_token = max(ent.start - window, 0)
                end_token = min(ent.end + window, len(doc))
                context_tokens = [t.text for t in doc[start_token:ent.start]]  # before entity
                context_tokens.append(f"[{ent.text}]")                          # entity itself
                context_tokens += [t.text for t in doc[ent.end:end_token]]      # after entity
                contexts.append((ent.text, " ".join(context_tokens)))
        
        return contexts