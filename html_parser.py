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


class HskHtmlParserFrench(HTMLParser):
    """
    Class for reading HTML HSK data
    """
    
    def __init__(self, u8_file):
        super().__init__()
        self.dict_content = {}
        self.grammar_indicator = None

    
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
    
    def check_grammar_indicators(self):
        """
        Parse the entries in self.dict_content for grammar indicator,
        replaces them with the french translations.
        Updates self.grammar_indicator
        Returns None
        """
        self.grammar_indicator = {
            "(助动词)": "(auxiliary verb)",
            "(助词)": "(particle)",
            "(动词)": "(verb)",
            "(叹词)": "(interjection)",
            "(形容词)": "(adjective)",
            "(介词)": "(preposition)",
            "(副词)": "(adverb)",
            "(名词)": "(noun)",
            "(量词)": "(quantifier)"
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
        deck = ET.Element('deck', attrib={'name': f'HSK {self.dict_content["hskLevel"]} Words'})

        fields = ET.SubElement(deck, 'fields')
        chinese = ET.SubElement(fields, 'chinese', attrib={'name': 'Chinese', 'sides': '10', 'lang': 'zh-CN', 'pinyinMode': 'back'})
        text = ET.SubElement(fields, 'text', attrib={'name': 'Translation', 'sides': '01', 'lang': 'en-EN'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["words"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            if hanzi != word_entry["hanziRaw"]:
                # Replacing chinese grammar indicators
                for key, value in self.grammar_indicator.items():
                    hanzi = hanzi.replace(key, value)

            card = ET.SubElement(cards, "card")
            chinese = ET.SubElement(card, 'chinese', attrib={'name': 'Chinese'})
            chinese.text = hanzi
            text = ET.SubElement(card, 'text', attrib={'name': 'Translation'})
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
        chinese = ET.SubElement(fields, 'chinese', attrib={'name': 'Chinese', 'sides': '10', 'lang': 'zh-CN', 'pinyinMode': 'back'})
        text = ET.SubElement(fields, 'text', attrib={'name': 'Translation', 'sides': '01', 'lang': 'en-EN'})

        cards = ET.SubElement(deck, "cards")

        for word_entry in self.dict_content["localizedSentences"]:

            hanzi = word_entry["hanzi"]
            definition = word_entry["def"]

            card = ET.SubElement(cards, "card")
            chinese = ET.SubElement(card, 'chinese', attrib={'name': 'Chinese'})
            chinese.text = hanzi
            text = ET.SubElement(card, 'text', attrib={'name': 'Translation'})
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
                   Student
                   
        Front :    Student      
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
                      I am a student
                
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
