import sys
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.boundsPen import BoundsPen
out=sys.argv[1]
SIZE=100.0
def run(fontpath, text, x0, track_em=0.0):
    f=TTFont(fontpath); gs=f.getGlyphSet(); cmap=f.getBestCmap(); upm=f['head'].unitsPerEm; s=SIZE/upm
    hmtx=f['hmtx']; d=[]; x=x0; bounds=[]
    for ch in text:
        g=cmap[ord(ch)]; pen=SVGPathPen(gs); tp=TransformPen(pen,(s,0,0,-s,x,0)); gs[g].draw(tp); d.append(pen.getCommands())
        bp=BoundsPen(gs); gs[g].draw(TransformPen(bp,(s,0,0,-s,x,0)));
        if bp.bounds: bounds.append(bp.bounds)
        x+=hmtx[g][0]*s + track_em*SIZE
    return ' '.join(d), x, bounds
d1,x,b1=run('/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf','beyond',0,-0.02)
d2,x2,b2=run('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf','404',x+0.0)
bb=b1+b2; minx=min(b[0] for b in bb); miny=min(b[1] for b in bb); maxx=max(b[2] for b in bb); maxy=max(b[3] for b in bb)
pad=0; vb=f'{minx-pad:.2f} {miny-pad:.2f} {maxx-minx+2*pad:.2f} {maxy-miny+2*pad:.2f}'
W=maxx-minx; H=maxy-miny
def svg(ink,acc,bg=None,padf=0.0):
    p=padf*H; v=f'{minx-p:.2f} {miny-p:.2f} {W+2*p:.2f} {H+2*p:.2f}'
    rect=f'<rect x="{minx-p:.2f}" y="{miny-p:.2f}" width="{W+2*p:.2f}" height="{H+2*p:.2f}" fill="{bg}"/>' if bg else ''
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{v}" width="{(W+2*p)*4:.0f}" height="{(H+2*p)*4:.0f}" role="img" aria-label="beyond404"><title>beyond404</title>{rect}<path fill="{ink}" d="{d1}"/><path fill="{acc}" d="{d2}"/></svg>'
INK='#141a22'; ACC='#d6461f'
open(f'{out}/beyond404-logo.svg','w').write(svg(INK,ACC))
open(f'{out}/beyond404-logo-white-bg.svg','w').write(svg(INK,ACC,'#ffffff',0.6))
open(f'{out}/beyond404-logo-negative.svg','w').write(svg('#ffffff','#ff6a3d'))
open(f'{out}/beyond404-logo-black.svg','w').write(svg('#000000','#000000'))
print(W,H)
