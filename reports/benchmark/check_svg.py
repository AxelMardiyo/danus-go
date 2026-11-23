import xml.etree.ElementTree as ET
import glob

def test_bb_overlap(path):
    tree = ET.parse(path)
    root = tree.getroot()
    boxes = []
    for elem in root.iter():
        if elem.tag.endswith('text') and elem.text:
            txt = elem.text.strip()
            x = float(elem.get('x', 0))
            y = float(elem.get('y', 0))
            anchor = elem.get('text-anchor', 'start')
            size = float(elem.get('font-size', '12'))
            # Approximate char width generously (0.65 of font size)
            width = len(txt) * size * 0.65
            height = size * 1.15
            if anchor == 'middle':
                left = x - width / 2.0
            elif anchor == 'end':
                left = x - width
            else:
                left = x
            right = left + width
            top = y - height
            bottom = y
            boxes.append({'text': txt, 'box': (left, top, right, bottom), 'size': size})
            
    overlaps = []
    for i in range(len(boxes)):
        for j in range(i+1, len(boxes)):
            b1 = boxes[i]['box']
            b2 = boxes[j]['box']
            # Check bounding box intersection
            if not (b1[2] < b2[0] or b1[0] > b2[2] or b1[3] < b2[1] or b1[1] > b2[3]):
                overlaps.append((boxes[i]['text'], boxes[j]['text']))
    print(f"=== {path} ===")
    if not overlaps:
        print("  -> 0 Bounding Box Overlaps (PERFECT ZERO COLLISION)")
    else:
        print(f"  -> {len(overlaps)} overlaps detected:")
        for o in overlaps:
            print(f"     '{o[0]}' overlaps with '{o[1]}'")

for f in sorted(glob.glob('reports/figures/*.svg')):
    test_bb_overlap(f)
