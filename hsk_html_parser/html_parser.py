"""
Custom HTMLParser class for extracting HSK words and translating them to French
"""

import ast
import logging
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

import pandas as pd

logging.basicConfig(
    encoding="utf-8",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

"""
Structure of the .u8 Chinese -> French dictionary
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


class ChineseToFrenchDictionary:
    """
    Class for creating a Chinese --> French dictionary
    # as a dataframe
    """

    def __init__(self, u8_file):
        # A dictionary for corresponding pinyins
        # to their accents, e.g. i3 -> ǐ
        self.pinyin_tone = {
            "a": "a\u0101\u00e1\u01ce\u00e0a",
            "e": "e\u0113\u00e9\u011b\u00e8e",
            "i": "i\u012b\u00ed\u01d0\u00eci",
            "o": "o\u014d\u00f3\u01d2\u00f2o",
            "u": "u\u016b\u00fa\u01d4\u00f9u",
            "\u00fc": "\u00fc\u01d6\u01d8\u01da\u01dc\u00fc",
        }  # accent 5 corresponds to no accent at all

        # Regular expressions used to find pinyins
        # and vowels with accent in words
        self.pinyin_re = re.compile(r"[a-zA-Z:]+\d")
        self.vowels_re = re.compile(r"[aeiou\u00fc]+")  # find all vowels

        # Puts the dictionary data in a DataFrame
        self.df = self.process_u8_dictionary(u8_file)

    def process_u8_dictionary(self, u8_file):
        """
        Creates a dataframe serving as a Chinese->French dictionary
           Simplified 	Pinyin 	      Translation
        0     精美 	  jīng měi 	élégant ; exquis ; délicat ; gracieux ; délici...
        1     亲近 	  qīn jìn 	proche ; intime
        2     修改 	  xiū gǎi 	réviser ; modifier ; éditer

        Positionnal arguments:
        u8_file (str) -- The path to the u8_file containing the original dictionary.
        Returns a pandas.DataFrame
        """

        with open(u8_file, encoding="utf-8") as file:
            lines = [k[:-2] for k in file.readlines() if k[0] != "#"]

        lines_data = [
            [
                l.split(" ")[1].strip(),
                self.format_pinyin(l.split("[")[1].split("]")[0]).strip(),
                " ; ".join(l.split("/")[1:]),
            ]
            for l in lines
        ]
        return pd.DataFrame(
            columns=["Simplified", "Pinyin", "Translation"], data=lines_data
        )

    def format_pinyin(self, pinyins):
        """
        Converts numeral pinyins to accent pinyins.
        For instance  'U S B shou3 zhi3' --> 'U S B shǒu zhǐ'

        Positionnal arguments:
        u8_file (str) -- The path to the u8_file containing the original dictionary.
        Returns a str object, with the correct pinyin
        """
        try:
            new_pinyin = ""
            last_span = 0
            for particule in self.pinyin_re.finditer(pinyins):
                pinyin_correct = particule.group().lower().replace("v", "\u00fc")
                pinyin_correct = pinyin_correct.replace("u:", "\u00fc")
                vowels = self.vowels_re.search(pinyin_correct)
                # Check which letter to put accent on
                if (len(vowels.group()) == 1) or vowels.group()[0] in "aeo":
                    pinyin_correct = pinyin_correct.replace(
                        vowels.group()[0],
                        self.pinyin_tone[vowels.group()[0]][int(pinyin_correct[-1])],
                    )
                else:
                    pinyin_correct = pinyin_correct.replace(
                        vowels.group()[1],
                        self.pinyin_tone[vowels.group()[1]][int(pinyin_correct[-1])],
                    )
                new_pinyin += (
                    pinyins[last_span : particule.span()[0]] + pinyin_correct[:-1]
                )  # We do not take the last number
                last_span = particule.span()[1]

            if last_span != len(pinyins):
                new_pinyin += pinyins[last_span:]
            return new_pinyin
        except AttributeError:  # Typically xx5, n2, m2
            return pinyins


class HskHtmlParser(HTMLParser):  # pylint: disable=W0223
    """
    Class for reading HTML HSK data.
    """

    def __init__(self, translate_to_french=False, u8_file=None):
        super().__init__()
        self.content = {}
        self.grammar_indicator = None
        self.metadata = {
            "English": {
                "Translation": "Translation",
                "lang": "en-EN",
                "Chinese": "Chinese",
                "Sentences": "Sentences",
                "Word List": "Word List",
            },
            "French": {
                "Translation": "Traduction",
                "lang": "fr-FR",
                "Chinese": "Chinois",
                "Sentences": "Phrases",
                "Word List": "Vocabulaire",
            },
        }
        self.translate_to_french = translate_to_french
        if self.translate_to_french:
            self.metadata_key = "French"
            assert u8_file, "Must provide u8_file if translate_to_french=True"
            self.dictionary = ChineseToFrenchDictionary(u8_file)
        else:
            self.metadata_key = "English"
            self.dictionary = None

    def translate_content_to_french(self):
        """
        Swiches the english definition of each word (from HTML) to its french definition (from .u8)
        Returns None
        """
        for i in range(len(self.content["words"])):
            word = self.content["words"][i]["hanziRaw"].strip()
            sub_df = self.dictionary.df[self.dictionary.df["Simplified"] == word]

            if len(sub_df) > 1:
                sub_sub_df = sub_df[
                    sub_df["Pinyin"]
                    == self.content["words"][i]["pinyinToneSpace"].strip()
                ]
                if len(sub_sub_df) == 1:
                    self.content["words"][i]["def"] = sub_sub_df["Translation"].iloc[0]
                else:
                    logging.warning(
                        "Multiple translations for %s. Keeping the English translation.",
                        word,
                    )
            elif len(sub_df) == 0:
                logging.warning(
                    "%s has no French translation. Keeping the English translation.",
                    word,
                )
            else:
                self.content["words"][i]["def"] = sub_df["Translation"].iloc[0]

    def handle_data(self, data):
        """
        Overwrites handle_data method from parent HTMLParser class.
        Automatically called when parsing the html file, should not be called directly.
        This method is called to process arbitrary data (e.g. text nodes and the content
        of <script>...</script> and <style>...</style>)
        Updates self.content

        Positionnal arguments:
        data (str) --
        Returns None
        """
        if "window.__REACT_DATA = " in data:
            content = data.split("window.__REACT_DATA = ")[1][
                :-2
            ]  # removing the last ';'
            self.content = ast.literal_eval(content)
            self.check_grammar_indicators()
            if self.translate_to_french:
                self.translate_content_to_french()

    def check_grammar_indicators(self):
        """
        Parse the entries in self.content for grammar indicator,
        replaces them with the french translations.
        Updates self.grammar_indicator
        Returns None
        """
        if self.translate_to_french:
            self.grammar_indicator = {
                "(助动词)": "(verbe auxiliaire)",
                "(助词)": "(particule)",
                "(动词)": "(verbe)",
                "(叹词)": "(interjection)",
                "(形容词)": "(adjectif)",
                "(介词)": "(préposition)",
                "(副词)": "(adverbe)",
                "(名词)": "(nom)",
                "(量词)": "(quantificateur)",
            }
        else:
            self.grammar_indicator = {
                "(助动词)": "(auxiliary verb)",
                "(助词)": "(particle)",
                "(动词)": "(verb)",
                "(叹词)": "(interjection)",
                "(形容词)": "(adjective)",
                "(介词)": "(preposition)",
                "(副词)": "(adverb)",
                "(名词)": "(noun)",
                "(量词)": "(quantifier)",
            }

        # Checking if there are other indicators like '(助词)' in
        # the data that are not already in grammar_indicator
        parenthesis_regex = re.compile(r"\(.*?\)")
        list_missing_indicator = []
        for word_entry in self.content["words"]:
            if word_entry["hanzi"] != word_entry["hanziRaw"]:
                parenthesis_words = parenthesis_regex.findall(word_entry["hanzi"])
                if parenthesis_words:
                    list_missing_indicator += [
                        k for k in parenthesis_words if k not in self.grammar_indicator
                    ]

        list_missing_indicator = list(
            set(list_missing_indicator)
        )  # Removing duplicates
        if len(list_missing_indicator) > 0:
            logger.warning("Missing grammar indicators: %s", list_missing_indicator)

    def create_word_xml_automatic(self, output_file):
        """
        Create a AnkiApp Chinese deck with words from the HTML HSK file.
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element(
            "deck",
            attrib={
                "name": (
                    f'HSK {self.content["hskLevel"]} '
                    f'{self.metadata[self.metadata_key]["Word List"]}'
                )
            },
        )

        fields = ET.SubElement(deck, "fields")
        ET.SubElement(
            fields,
            "chinese",
            attrib={
                "name": self.metadata[self.metadata_key]["Chinese"],
                "sides": "10",
                "lang": "zh-CN",
                "pinyinMode": "back",
            },
        )
        ET.SubElement(
            fields,
            "text",
            attrib={
                "name": self.metadata[self.metadata_key]["Translation"],
                "sides": "01",
                "lang": self.metadata[self.metadata_key]["lang"],
            },
        )

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.content["words"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            if hanzi != word_entry["hanziRaw"]:
                # Replacing chinese grammar indicators
                for key, value in self.grammar_indicator.items():
                    hanzi = hanzi.replace(key, value)

            card = ET.SubElement(cards, "card")
            ET.SubElement(
                card,
                "chinese",
                attrib={"name": self.metadata[self.metadata_key]["Chinese"]},
            ).text = hanzi
            ET.SubElement(
                card,
                "text",
                attrib={"name": self.metadata[self.metadata_key]["Translation"]},
            ).text = definition

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")

    def create_sentence_xml_automatic(self, output_file):
        """
        Create a AnkiApp Chinese deck with sentences from the HTML HSK file.
        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element(
            "deck",
            attrib={
                "name": (
                    f'HSK {self.content["hskLevel"]} '
                    f'{self.metadata[self.metadata_key]["Sentences"]}'
                )
            },
        )

        fields = ET.SubElement(deck, "fields")
        ET.SubElement(
            fields,
            "chinese",
            attrib={
                "name": self.metadata[self.metadata_key]["Chinese"],
                "sides": "10",
                "lang": "zh-CN",
                "pinyinMode": "back",
            },
        )
        ET.SubElement(
            fields,
            "text",
            attrib={
                "name": self.metadata[self.metadata_key]["Translation"],
                "sides": "01",
                "lang": self.metadata[self.metadata_key]["lang"],
            },
        )

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.content["localizedSentences"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            card = ET.SubElement(cards, "card")
            ET.SubElement(
                card,
                "chinese",
                attrib={"name": self.metadata[self.metadata_key]["Chinese"]},
            ).text = hanzi
            ET.SubElement(
                card,
                "text",
                attrib={"name": self.metadata[self.metadata_key]["Translation"]},
            ).text = definition

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")

    def create_word_xml(self, output_file):
        """
        Create a AnkiApp text deck with words from the HTML HSK file.
        The difference with self.create_word_xml_automatic is that two cards
        are created for each word, so that pinyins are always on the back side:
        Front :      学生
        Back  :   xué shēng
                   Student

        Front :    Student
        Back  :   xué shēng
                     学生

        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element(
            "deck",
            attrib={
                "name": (
                    f'HSK {self.content["hskLevel"]} '
                    f'{self.metadata[self.metadata_key]["Word List"]}'
                )
            },
        )

        fields = ET.SubElement(deck, "fields")
        ET.SubElement(
            fields, "text", attrib={"name": "Front", "sides": "11", "lang": "zh-CN"}
        )  # Visible on both sides
        ET.SubElement(
            fields, "text", attrib={"name": "Back", "sides": "01", "lang": "zh-CN"}
        )
        ET.SubElement(fields, "rich-text", attrib={"name": "Pinyin", "sides": "01"})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.content["words"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]
            pinyin_accent = word_entry["pinyinToneSpace"]

            if hanzi != word_entry["hanziRaw"]:
                # Replacing chinese grammar indicators
                for key, value in self.grammar_indicator.items():
                    hanzi = hanzi.replace(key, value)

            card = ET.SubElement(cards, "card")
            ET.SubElement(card, "text", attrib={"name": "Front"}).text = hanzi
            ET.SubElement(card, "text", attrib={"name": "Back"}).text = definition
            pinyin = ET.SubElement(card, "rich-text", attrib={"name": "Pinyin"})
            ET.SubElement(pinyin, "i").text = pinyin_accent

            card = ET.SubElement(cards, "card")
            ET.SubElement(card, "text", attrib={"name": "Front"}).text = definition
            ET.SubElement(card, "text", attrib={"name": "Back"}).text = hanzi
            pinyin = ET.SubElement(card, "rich-text", attrib={"name": "Pinyin"})
            ET.SubElement(pinyin, "i").text = pinyin_accent

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
                    I am a student

        Positionnal arguments:
        output_file (str) -- Path to the output .xml file
        Returns None
        """
        deck = ET.Element(
            "deck",
            attrib={
                "name": (
                    f'HSK {self.content["hskLevel"]} '
                    f'{self.metadata[self.metadata_key]["Sentences"]}'
                )
            },
        )

        fields = ET.SubElement(deck, "fields")
        ET.SubElement(
            fields, "text", attrib={"name": "Front", "sides": "11", "lang": "zh-CN"}
        )  # Visible on both sides
        ET.SubElement(
            fields, "text", attrib={"name": "Back", "sides": "01", "lang": "zh-CN"}
        )
        ET.SubElement(fields, "rich-text", attrib={"name": "Pinyin", "sides": "01"})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.content["localizedSentences"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]
            pinyin_accent = word_entry["pinyinTone"]

            card = ET.SubElement(cards, "card")
            ET.SubElement(card, "text", attrib={"name": "Front"}).text = hanzi
            ET.SubElement(card, "text", attrib={"name": "Back"}).text = definition
            pinyin = ET.SubElement(card, "rich-text", attrib={"name": "Pinyin"})
            ET.SubElement(pinyin, "i").text = pinyin_accent

        deck_tree = ET.ElementTree(deck)
        deck_tree.write(output_file, encoding="unicode")
