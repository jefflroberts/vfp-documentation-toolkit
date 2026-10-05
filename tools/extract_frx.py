"""
Extract a VFP .frx report layout straight from the report (a DBF) and regenerate the page
geometry with a coordinate-draw engine (ReportLab). This is the highest-fidelity migration path
for a report — driven by the FRX's own coordinates, not re-eyeballed or re-implemented in CSS.

Writes two files into --out, named after the FRX:
  <frxstem>_layout.json          the structured layout spec
  <frxstem>_reconstruction.pdf   a geometry skeleton drawn from the coordinates

FRX coordinates are in 1/10000 inch. ReportLab uses points (1/72 inch).

Usage:
    python extract_frx.py --frx "C:\\path\\to\\report.frx" [--out <dir>]
    # --out defaults to this script's directory.
"""
import sys, os, json, argparse
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)      # the vendored dbf.py sits beside this script
from dbf import read_table
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

FRU = 10000.0          # FRX units per inch
def to_pt(v): return (v / FRU) * 72.0 if v is not None else 0.0

def classify(r):
    ot = r.get('objtype')
    expr = (r.get('expr') or '').strip()
    pic = (r.get('picture') or '').strip()
    if ot == 1:   return 'pagesetup'
    if ot == 9:   return 'band'
    if ot == 17:  return 'picture'
    if ot == 6:   return 'line'
    if ot == 7:   return 'box'
    if ot in (5, 8):
        # literal "quoted" expr => label; field/expression reference => field
        return 'label' if expr.startswith('"') else 'field'
    return 'other'

def main(frx, out):
    _, rows = read_table(frx)
    stem = os.path.splitext(os.path.basename(frx))[0]
    layout_path = os.path.join(out, stem + '_layout.json')
    recon_path = os.path.join(out, stem + '_reconstruction.pdf')
    objs = []
    pagesetup = {}
    bands = []
    for r in rows:
        kind = classify(r)
        if kind == 'pagesetup':
            pagesetup = {'raw': (r.get('expr') or '').replace('\r\n', '; ')}
            continue
        if kind == 'band':
            bands.append({'objcode': r.get('objcode'), 'height_fru': r.get('height')})
            continue
        if kind == 'other':
            continue
        objs.append({
            'kind': kind,
            'vpos': r.get('vpos'), 'hpos': r.get('hpos'),
            'height': r.get('height'), 'width': r.get('width'),
            'name': (r.get('name') or '').strip(),          # picture sources live here
            'expr': (r.get('expr') or '').strip(),
            'supexpr': (r.get('supexpr') or '').strip(),   # print-when condition
            'picture': (r.get('picture') or '').strip(),
            'fontface': (r.get('fontface') or '').strip(),
            'fontsize': r.get('fontsize'),
            'fontstyle': r.get('fontstyle'),
        })

    # ---- structured layout JSON (the extracted spec) ----
    layout = {'source': os.path.basename(frx), 'pagesetup': pagesetup,
              'bands': bands, 'object_counts': {}, 'objects': objs}
    for o in objs:
        layout['object_counts'][o['kind']] = layout['object_counts'].get(o['kind'], 0) + 1
    with open(layout_path, 'w') as f:
        json.dump(layout, f, indent=1)

    # ---- coordinate-draw reconstruction (geometry skeleton) ----
    pw, ph = letter   # 612 x 792 pt
    c = canvas.Canvas(recon_path, pagesize=letter)
    placed = {'picture': 0, 'line': 0, 'box': 0, 'label': 0, 'field': 0, 'skipped_nopos': 0}
    for o in objs:
        if o['vpos'] is None or o['hpos'] is None:
            placed['skipped_nopos'] += 1; continue
        x = to_pt(o['hpos']); w = to_pt(o['width'] or 0)
        h = to_pt(o['height'] or 0)
        y = ph - to_pt(o['vpos']) - h     # FRX origin = top-left; PDF = bottom-left
        k = o['kind']
        if k == 'picture':
            c.setStrokeColorRGB(0.1, 0.4, 0.9); c.setLineWidth(0.8)
            c.rect(x, y, w, h)
            c.setFillColorRGB(0.1, 0.4, 0.9); c.setFont('Helvetica', 4)
            nm = os.path.basename((o['picture'] or o['expr']).strip('"').replace('\\', '/')) or 'img'
            c.drawString(x + 1, y + h - 5, f"IMG:{nm[:22]}")
            placed['picture'] += 1
        elif k == 'line':
            c.setStrokeColorRGB(0, 0, 0); c.setLineWidth(max(0.3, h or 0.3))
            c.line(x, ph - to_pt(o['vpos']), x + w, ph - to_pt(o['vpos']))
            placed['line'] += 1
        elif k == 'box':
            c.setStrokeColorRGB(0.2, 0.2, 0.2); c.setLineWidth(0.6); c.rect(x, y, w, h)
            placed['box'] += 1
        else:  # label / field
            txt = o['expr'].strip('"')
            if k == 'field':
                txt = '[' + txt.split('.')[-1][:18] + ']'   # placeholder for the data value
            fs = max(3.5, min(to_pt(o['height'] or 1000), 10))
            c.setFillColorRGB(0, 0, 0)
            try:
                c.setFont('Helvetica-Bold' if (o['fontstyle'] or 0) & 1 else 'Helvetica', fs)
            except Exception:
                c.setFont('Helvetica', fs)
            c.drawString(x, y + 1, txt[:40])
            placed[k] += 1
    c.showPage(); c.save()

    print("=== FRX extraction ===")
    print(f"page setup: {pagesetup.get('raw', '')[:80]}")
    print(f"bands: {len(bands)}  ->", [(b['objcode'], round(b['height_fru'] or 0)) for b in bands])
    print(f"object counts: {layout['object_counts']}")
    print(f"placed onto reconstruction PDF: {placed}")
    # picture objects: positions + print-when conditions (image-placement reference)
    print("\n=== picture objects (position / size / print-when) ===")
    pics = [o for o in objs if o['kind'] == 'picture']
    for o in pics:
        src = os.path.basename((o['picture'] or o['expr']).strip('"').replace('\\', '/'))
        cond = o['supexpr'][:48]
        print(f"  {src:22} pos=({round(o['hpos'])},{round(o['vpos'])}) "
              f"size=({round(o['width'])}x{round(o['height'])})  print-when: {cond!r}")
    print(f"\nwrote: {os.path.basename(layout_path)}, {os.path.basename(recon_path)} in {out}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser(
        description="Extract a VFP .frx report layout to JSON + a coordinate-draw reconstruction PDF.")
    ap.add_argument('--frx', required=True, help='path to the .frx report (itself a DBF)')
    ap.add_argument('--out', default=_HERE,
                    help='output directory for the JSON + PDF (default: this script dir)')
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    main(args.frx, args.out)
