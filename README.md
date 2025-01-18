# README

This repo is meant to automatically create HSK revision decks for AnkiApp. French Decks are available in `xml_outputs/`.


To re-create your own deck, you need to download html source code of [this page](https://hsk.academy/fr/hsk-1-vocabulary-list).
If it does not work, copy this link: `https://hsk.academy/fr/hsk-1-vocabulary-list`.
Then save the `html` data locally. `Create_flashcards.ipynb` allows to parse the html data, extract the word list, and create a `.xml` file to import in AnkiApp.

Note that there are two type of deck being created: one for HSK words (vocabulary list), and one for practice sentences.

### If you want to use non French decks (English, Arab, etc.) you can change the language of the html page on the website. Some minor tweeking to the notebook might be required (namely in the language attributes of `xml` elements, as well as the `grammar_indicator` dictionnary. 

AnkiApp allows to automatically detect Pinyin, decks `xml_outputs/automatic_pinyin/` are tailored for this functionnality.
### However, the detected pinyin are often wrong. I thus created custom decks with the correct pinyin
The problem is that there is no way to always show pinyin on the back of the card in "alternate" revision mode. For "words" decks, the custom decks thus have every word in double, one for the French -> Chinese revision, one for the Chinese -> French revision. Sentences decks are only meant to be Chinese -> French, so cards are not duplicated.

# Some usefull info on how the data is organised
## Structure of the content dictionnary extracted from the `html` data

### 1. Key `word`
Contains a list of dictionnaries.
Each dictionnary has 8 keys:

`'id'`, `'hanzi'`, `'hanziRaw'`, `'trad'`, `'pinyinToneSpace'`, `'def'`, `'mp3File'`, `'oggFile'`

Example of a dictionnary:
```
{'id': 684,
 'hanzi': '得(助动词)',
 'hanziRaw': '得',
 'trad': '得(助動詞)',
 'pinyinToneSpace': 'dé',
 'def': 'devoir, pouvoir (particule utilisée pour exprimer la possibilité, la capacité, l’effet, le degré)',
 'mp3File': '得(助动词).mp3',
 'oggFile': '得(助动词).ogg'
}

```

- `id` contains just the number of the entry. 
- `hanzi` contains the chinese character (simplified), with indication of auxiliary particules (助词) or auxiliary verbs (助动词) etc.
- `hanziRaw` contains the chinese character whitout indication of auxiliary particules (助词) etc. 
- `trad` contains the traditionnal hanzi.
- `pinyinToneSpace` contains the pinyin.
- `def` contains the definition/translation
- `mp3file` contains the name of the mp3 file with the audio of the word.
- `oggFile` contains the name of the ogg file with the audio of the word.

### 2. Key `wordIdToCharacters` (useless)
Contains a dictionnary whose keys are the `id`s of every word, and the content are the decomposition of the world into different characters
Example of `(key, value)` pairs:
```
'762': [{'slug': '果', 'hanzi': '果', 'wordId': 762},
        {'slug': '汁', 'hanzi': '汁', 'wordId': 762}],
'684': [{'slug': '得', 'hanzi': '得', 'wordId': 684}],
```
It seems that `slug` and `hanzi` values are always the same.

### 3. Key `localizedSentences`
Contains a list of dictionnaries. Each dictionnary has three keys: 
`'hanzi'`, `'pinyinTone'`, `'def'`
Example:
```
{'hanzi': '你把火点着吧。',
 'pinyinTone': 'Nǐ bǎ huǒ diǎnzhe ba.',
 'def': 'Vous allumez le feu.'
}
```

### 4. Key `hskLevel`
The corresponding HSK level, i.e. `4` for instance.


## Desired structure of the `.xml` file
(two possible structure for a card):

```
<deck name="Chinois">
    <fields>
        <chinese name='Chinois' sides='11' lang='zh-CN'  pinyinMode='hint'></chinese>
        <text name='Traduction' sides='01' lang='fr-FR'></text>
    </fields>
    <cards>
        <card>
            <chinese name='Chinois'>月亮</chinese>
            <text name='Traduction'>Lune</text>
        </card>
        <card>
            <chinese name='Chinois'>
                <chinese>介绍</chinese>
            </chinese>
            <text name='Traduction'>Introduire, présenter qqun </text>
        </card>
    </cards>
</deck>
```
