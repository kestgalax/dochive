from dochive.markdown_normalizer import normalize_markdown


def test_drops_copy_link_before_fenced_code() -> None:
    markdown = """
[Copy](./change_list_arch_281)

```
"userCatalog" : [
"uuid" : "analyticalCat$38378701",
]
```
"""

    assert normalize_markdown(markdown) == '''```
"userCatalog" : [
"uuid" : "analyticalCat$38378701",
]
```
'''


def test_keeps_regular_copy_link_away_from_code() -> None:
    markdown = """
See [Copy](./copy-page) for details.

Regular paragraph.
"""

    assert normalize_markdown(markdown) == "See [Copy](./copy-page) for details.\n\nRegular paragraph.\n"
