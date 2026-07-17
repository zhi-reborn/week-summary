from copy import deepcopy
from typing import Any

from lxml import etree  # type: ignore[import-untyped]

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_XML = "http://www.w3.org/XML/1998/namespace"


def copy_paragraph_properties(source: Any, target: Any) -> None:
    properties = source.find(f"{{{_W}}}pPr")
    if properties is not None:
        target.append(deepcopy(properties))


def append_inherited_run(paragraph: Any, source_run: Any, text: str) -> None:
    run = etree.SubElement(paragraph, f"{{{_W}}}r")
    properties = source_run.find(f"{{{_W}}}rPr") if source_run is not None else None
    if properties is not None:
        run.append(deepcopy(properties))
    node = etree.SubElement(run, f"{{{_W}}}t")
    node.text = text
    if text[:1].isspace() or text[-1:].isspace():
        node.set(f"{{{_XML}}}space", "preserve")
