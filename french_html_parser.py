import ast
import io
import logging
import os
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pandas as pd

logging.basicConfig(encoding='utf-8', level=logging.INFO, format="%(asctime)s - %(levelname)s: %(message)s", datefmt='%Y/%m/%d %H:%M:%S')
logger = logging.getLogger(__name__)


"""
Structure of the .u8 Chinese -> French dictionnary 
Traditionnel Simplifié [pin1 yin1] /traduction 1/traduction2/...

中國 中国 [Zhong1 guo2] /Chine/Empire du Milieu/

Placement of the pinyin tone mark
|     |   -a    | -e  | -i  | -o  | -u  |
|:---:|:-------:|:---:|:---:|:---:|:---:|
| a-  |         |     |  ài | ào  |     |
| e-  |         |     | èi  |     |     |
| i-  | ià, iào |  iè |     |  iò | iù  |
| o-  |         |     |     |     | òu  |
| u-  | uà, uài |  uè |  uì | uò  |     |
| ü-  |   (üà)  | üè  |     |     |     |
"""

class HskHtmlParserFrench(HTMLParser):
    """
    Class for reading HTML HSK data as well as Chinese->French dictionnary 
    """
    
    def __init__(self, u8_file):
        super().__init__()
        self.dict_content = {}
        self.grammar_indicator = None
        
        # A dictionnary for corresponding pinyins
        # to their accents, e.g. i3 -> ǐ
        self.pinyin_tone = {
            "a": "a\u0101\u00e1\u01ce\u00e0a",
            "e": "e\u0113\u00e9\u011b\u00e8e",
            "i": "i\u012b\u00ed\u01d0\u00eci",
            "o": "o\u014d\u00f3\u01d2\u00f2o",
            "u": "u\u016b\u00fa\u01d4\u00f9u",
            "\u00fc": "\u00fc\u01d6\u01d8\u01da\u01dc\u00fc"
        }  # accent 5 corresponds to no accent at all
        
        # Regular expressions used to find pinyins
        # and vowels with accent in words
        self.pinyin_re = re.compile(r"[a-zA-Z:]+\d")
        self.vowels_re = re.compile(r"[aeiou\u00fc]+")  # find all vowels
        
        # Puts the dictionnary data in a DataFrame
        self.df = self.process_u8_dictionnary(u8_file)
        
        
    def process_u8_dictionnary(self, u8_file):
        """
        Creates a dataframe serving as a Chinese->French dictionnary
           Simplified 	Pinyin 	      Translation
        0     精美 	  jīng měi 	élégant ; exquis ; délicat ; gracieux ; délici...
        1     亲近 	  qīn jìn 	proche ; intime
        2     修改 	  xiū gǎi 	réviser ; modifier ; éditer
        
        Positionnal arguments:
        u8_file (str) -- The path to the u8_file containing the original dictionnary.
        Returns a pandas.DataFrame
        """

        with open(u8_file) as f:
            lines = [k[:-2] for k in f.readlines() if k[0]!="#"]

        lines_data =[[l.split(" ")[1].strip(), self.format_pinyin(l.split("[")[1].split("]")[0]).strip(), " ; ".join(l.split("/")[1:])] for l in lines]
        return pd.DataFrame(columns=["Simplified", "Pinyin", "Translation"], data=lines_data)

    def format_pinyin(self,pinyins):
        """
        Converts numeral pinyins to accent pinyins.
        For instance  'U S B shou3 zhi3' --> 'U S B shǒu zhǐ'
        
        Positionnal arguments:
        u8_file (str) -- The path to the u8_file containing the original dictionnary.
        Returns a str object, with the correct pinyin
        """
        try:
            new_pinyin = ""
            last_span = 0
            for particule in self.pinyin_re.finditer(pinyins):
                pinyin_correct = particule.group().lower().replace("v", "\u00fc")
                pinyin_correct = pinyin_correct.replace("u:", "\u00fc")
                accent = int(pinyin_correct[-1])
                vowels = self.vowels_re.search(pinyin_correct)
                # Check which letter to put pinyin on    
                if (len(vowels.group())==1) or vowels.group()[0] in "aeo":
                    pinyin_correct = pinyin_correct.replace(vowels.group()[0],
                                                            self.pinyin_tone[vowels.group()[0]][int(pinyin_correct[-1])])
                else:
                    pinyin_correct = pinyin_correct.replace(vowels.group()[1],
                                                            self.pinyin_tone[vowels.group()[1]][int(pinyin_correct[-1])])
                new_pinyin += pinyins[last_span:particule.span()[0]] + pinyin_correct[:-1] # We do not take the last number
                last_span = particule.span()[1]

            if last_span != len(pinyins):
                new_pinyin += pinyins[last_span:]
            return new_pinyin
        except AttributeError:  # Typically xx5, n2, m2
            return pinyins
    
    def translate_entry_to_french(self):
        """
        Swiches the english definition of each word (from HTML) to its french definition (from .u8)
        Returns None
        """
        for entry in self.dict_content["words"]:
            word = entry["hanziRaw"].strip()
            sub_df = self.df[self.df["Simplified"]==word]

            if len(sub_df)>1:
                sub_sub_df = sub_df[sub_df["Pinyin"]==entry["pinyinToneSpace"].strip()]
                if len(sub_sub_df)==1:
                    self.dict_content["def"] = sub_sub_df["Translation"].iloc[0]
                else:
                    logging.warning(f"Multiple translations for {word}. Keeping the English translation.")
            elif len(sub_df)==0:
                logging.warning(f"{word} has no French translation. Keeping the English translation.")

    
    def handle_data(self, data):
        """
        Overwrites handle_data method from parent HTMLParser class.
        Automatically called when parsing the html file, should not be called directly.
        This method is called to process arbitrary data (e.g. text nodes and the content
        of <script>...</script> and <style>...</style>)
        Updates self.dict_content
        
        Positionnal arguments:
        data (str) --
        Returns None
        """
        if "window.__REACT_DATA = " in data:
            content = data.split("window.__REACT_DATA = ")[1][:-2]  # removing the last ';'
            self.dict_content = ast.literal_eval(content)
            self.check_grammar_indicators()
            self.translate_entry_to_french()
    
    def check_grammar_indicators(self):
        """
        Parse the entries in self.dict_content for grammar indicator,
        replaces them with the french translations.
        Updates self.grammar_indicator
        Returns None
        """
        self.grammar_indicator = {
            "(助动词)": "(verbe auxiliaire)",
            "(助词)": "(particule)",
            "(动词)": "(verbe)",
            "(叹词)": "(interjection)",
            "(形容词)": "(adjectif)",
            "(介词)": "(préposition)",
            "(副词)": "(adverbe)",
            "(名词)": "(nom)",
            "(量词)": "(quantificateur)"
        }
        
        # Checking if there are other indicators like '(助词)' in
        # the data that are not already in grammar_indicator
        parenthesis_regex = re.compile("\(.*?\)")
        list_missing_indicator = []
        for word_entry in self.dict_content["words"]:
            if word_entry["hanzi"] != word_entry["hanziRaw"]:
                parenthesis_words = parenthesis_regex.findall(word_entry["hanzi"])
                if parenthesis_words:
                    list_missing_indicator += [k for k in parenthesis_words if k not in self.grammar_indicator.keys()]
        
        list_missing_indicator = list(set(list_missing_indicator)) # Removing duplicates
        if len(list_missing_indicator)>0:
            logger.warning(f"Missing grammar indicators: {list_missing_indicator}")
        
            
    def create_word_xml_automatic(self, output_file):
        """
        Create a AnkiApp Chinese deck with words from the HTML HSK file.
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element('deck', attrib={'name': f'HSK {self.dict_content["hskLevel"]} Vocabulaire'})

        fields = ET.SubElement(deck, 'fields')
        chinese = ET.SubElement(fields, 'chinese', attrib={'name': 'Chinois', 'sides': '10', 'lang': 'zh-CN', 'pinyinMode': 'back'})
        text = ET.SubElement(fields, 'text', attrib={'name': 'Traduction', 'sides': '01', 'lang': 'fr-FR'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["words"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            if hanzi != word_entry["hanziRaw"]:
                # Replacing chinese grammar indicators
                for key, value in self.grammar_indicator.items():
                    hanzi = hanzi.replace(key, value)

            card = ET.SubElement(cards, "card")
            chinese = ET.SubElement(card, 'chinese', attrib={'name': 'Chinois'})
            chinese.text = hanzi
            text = ET.SubElement(card, 'text', attrib={'name': 'Traduction'})
            text.text = definition

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")

    def create_sentence_xml_automatic(self, output_file):
        """
        Create a AnkiApp Chinese deck with sentences from the HTML HSK file.
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element('deck', attrib={'name': f'HSK {self.dict_content["hskLevel"]} Phrases'})

        fields = ET.SubElement(deck, 'fields')
        chinese = ET.SubElement(fields, 'chinese', attrib={'name': 'Chinois', 'sides': '10', 'lang': 'zh-CN', 'pinyinMode': 'back'})
        text = ET.SubElement(fields, 'text', attrib={'name': 'Traduction', 'sides': '01', 'lang': 'fr-FR'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["localizedSentences"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            card = ET.SubElement(cards, "card")
            chinese = ET.SubElement(card, 'chinese', attrib={'name': 'Chinois'})
            chinese.text = hanzi
            text = ET.SubElement(card, 'text', attrib={'name': 'Traduction'})
            text.text = definition

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")

    def create_word_xml(self, output_file):
        """
        Create a AnkiApp text deck with words from the HTML HSK file.
        The difference with self.create_word_xml_automatic is that two cards
        are created for each word, so that pinyins are always on the back side:
        Front :      学生      
        Back  :   xué shēng
                   Etudiant
                   
        Front :    Etudiant      
        Back  :   xué shēng
                     学生
        
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element('deck', attrib={'name': f'HSK {self.dict_content["hskLevel"]} Vocabulaire'})

        fields = ET.SubElement(deck, 'fields')
        front = ET.SubElement(fields, 'text', attrib={'name': 'Front', 'sides': '11', 'lang': 'zh-CN'})  # Visible on both sides
        back = ET.SubElement(fields, 'text', attrib={'name': 'Back', 'sides': '01', 'lang': 'zh-CN'})
        pinyin = ET.SubElement(fields, 'rich-text', attrib={'name': 'Pinyin', 'sides': '01'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["words"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]
            pinyin_accent = word_entry["pinyinToneSpace"]

            if hanzi != word_entry["hanziRaw"]:
                # Replacing chinese grammar indicators
                for key, value in self.grammar_indicator.items():
                    hanzi = hanzi.replace(key, value)

            card = ET.SubElement(cards, "card")
            front = ET.SubElement(card, 'text', attrib={'name': 'Front'})
            front.text = hanzi
            back = ET.SubElement(card, 'text', attrib={'name': 'Back'})
            back.text = definition
            pinyin = ET.SubElement(card, 'rich-text', attrib={'name': 'Pinyin'})
            italic = ET.SubElement(pinyin, 'i')
            italic.text = pinyin_accent

            card = ET.SubElement(cards, "card")
            front = ET.SubElement(card, 'text', attrib={'name': 'Front'})
            front.text = definition
            back = ET.SubElement(card, 'text', attrib={'name': 'Back'})
            back.text = hanzi
            pinyin = ET.SubElement(card, 'rich-text', attrib={'name': 'Pinyin'})
            italic = ET.SubElement(pinyin, 'i')
            italic.text = pinyin_accent

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")

    def create_sentence_xml(self, output_file):
        """
        Create a AnkiApp text deck with sentences from the HTML HSK file.
        The difference with self.create_sentence_xml_automatic is that the
        pinyin on the back of the card is manually written
        so that it is always correct:
        Front :         我是一个学生      
        Back  :   wǒ shì yí gè xué shēng
                    Je suis un étudiant
                
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element('deck', attrib={'name': f'HSK {self.dict_content["hskLevel"]} Phrases'})

        fields = ET.SubElement(deck, 'fields')
        front = ET.SubElement(fields, 'text', attrib={'name': 'Front', 'sides': '11', 'lang': 'zh-CN'})  # Visible on both sides
        back = ET.SubElement(fields, 'text', attrib={'name': 'Back', 'sides': '01', 'lang': 'zh-CN'})
        pinyin = ET.SubElement(fields, 'rich-text', attrib={'name': 'Pinyin', 'sides': '01'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["localizedSentences"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]
            pinyin_accent = word_entry["pinyinTone"]

            card = ET.SubElement(cards, "card")
            front = ET.SubElement(card, 'text', attrib={'name': 'Front'})
            front.text = hanzi
            back = ET.SubElement(card, 'text', attrib={'name': 'Back'})
            back.text = definition
            pinyin = ET.SubElement(card, 'rich-text', attrib={'name': 'Pinyin'})
            italic = ET.SubElement(pinyin, 'i')
            italic.text = pinyin_accent

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")
