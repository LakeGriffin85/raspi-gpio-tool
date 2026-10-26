"""Generate documentation SVGs from the app's canonical pin/board models.

No GPIO access, photographs, screenshots or image-processing libraries are used.
"""
from html import escape
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from gpio_core import HEADER_GPIO, HEADER_POWER
from gpio_gertboard import GertboardDiagram
from gpio_i18n import set_language

OUT=ROOT/'docs/assets'


def svg(width,height,title,description,body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>'
            '<g font-family="DejaVu Sans,Arial,sans-serif">'+body+'</g></svg>\n')


def text(x,y,value,size=18,fill='#20364a',weight=400,anchor='start'):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>')


def banner():
    body='<rect width="1280" height="270" rx="22" fill="#102a38"/>'
    body+='<rect x="24" y="24" width="7" height="222" rx="3" fill="#35d1af"/>'
    body+=text(60,63,'A DESKTOP WORKSHOP FOR RASPBERRY PI 5',15,'#9ad5d0',700)
    body+=text(60,119,'Raspberry Pi GPIO Tool',43,'#f5fbff',700)
    body+=text(60,159,'See the pins. Understand the state. Control what you own.',21,'#c0d4df')
    for x,w,label in [(60,178,'English + Deutsch'),(252,166,'Live pin header'),(432,215,'Optional Gertboard')]:
        body+=f'<rect x="{x}" y="193" width="{w}" height="35" rx="17" fill="#1b4552"/>'
        body+=text(x+w/2,216,label,15,'#dbfbef',600,'middle')
    body+='<rect x="1053" y="34" width="162" height="200" rx="16" fill="#173e4a" stroke="#315967"/>'
    for row in range(8):
        for col in range(2):
            x=1092+col*68;y=59+row*21
            fill='#facc15' if row==col==0 else '#35d1af' if (row+col)%3 else '#8196a5'
            body+=f'<circle cx="{x}" cy="{y}" r="6" fill="{fill}"/>'
    body+=text(1134,249,'GPIO',13,'#9ad5d0',700,'middle')
    return svg(1280,270,'Raspberry Pi GPIO Tool','English and German desktop GPIO workshop with an optional Gertboard module.',body)


def pinout():
    body='<rect width="1280" height="910" rx="20" fill="#f3f7fa"/>'
    body+=text(38,52,'One header. Two numbering systems.',31,weight=700)
    body+=text(38,84,'Physical connector positions are different from BCM GPIO numbers.',18,'#536b7d')
    body+='<rect x="28" y="112" width="750" height="714" rx="16" fill="#ffffff" stroke="#d9e4eb"/>'
    body+='<rect x="285" y="143" width="230" height="596" rx="15" fill="#142d3e"/>'
    body+='<rect x="34" y="142" width="738" height="385" rx="10" fill="#dff3f0" fill-opacity=".45"/>'
    body+='<rect x="285" y="143" width="230" height="596" rx="15" fill="#142d3e"/>'
    colors={'3V3':'#d99413','5V':'#d64668','GND':'#8394a3'}
    for physical in range(1,41):
        row=(physical-1)//2;odd=bool(physical%2);y=164+row*29
        gpio=HEADER_GPIO.get(physical)
        label=f'GPIO{gpio}' if gpio is not None else HEADER_POWER[physical]
        if gpio in (0,1):label+=' / HAT ID'
        fill=colors.get(label,'#16a17a')
        if gpio in (0,1):fill='#9570dc'
        x=349 if odd else 451
        body+=f'<circle cx="{x}" cy="{y}" r="7" fill="{fill}"/>'
        if physical==1:body+=f'<circle cx="{x}" cy="{y}" r="13" fill="none" stroke="#facc15" stroke-width="4"/>'
        body+=text(314 if odd else 486,y+5,physical,14,'#facc15' if physical==1 else '#e5eef5',700,'middle')
        body+=text(258 if odd else 542,y+6,label,17,weight=600,anchor='end' if odd else 'start')
    body+='<path d="M746 145 h13 v379 h-13" fill="none" stroke="#109482" stroke-width="3"/>'
    body+=text(46,781,'Yellow ring = physical pin 1',18,weight=700)
    body+=text(46,807,'Static pinout reference — no live levels or voltage measurements.',14,'#536b7d')
    body+='<rect x="802" y="112" width="448" height="714" rx="16" fill="#ffffff" stroke="#d9e4eb"/>'
    body+=text(828,153,'GERTBOARD J1',16,'#0b8a78',700)
    body+=text(828,190,'26 contacts · 17 Pi signals',24,weight=700)
    body+=text(828,222,'The shaded first 13 rows are J1.',17)
    body+=text(828,249,'Pi positions 27–40 are outside J1.',17)
    body+=text(828,306,'A concrete example',20,weight=700)
    for y,label,sub in [(348,'Physical pin 11','Position on the connector'),(416,'BCM GPIO17','Number used by the app'),(484,'J2 · GP17','Legacy Gertboard signal label')]:
        body+=f'<rect x="826" y="{y-29}" width="397" height="55" rx="9" fill="#e9f4f3"/>'
        body+=text(844,y-5,label,18,weight=700)
        body+=text(844,y+16,sub,13,'#536b7d')
    body+=text(828,553,'B1 is buffer channel 1, not GPIO1.',17,weight=700)
    body+=text(828,583,'A patch wire assigns GP17 to B1.',16)
    body+=text(828,640,'Legacy board labels on Pi 5',18,weight=700)
    body+=text(828,674,'GP0 → GPIO2',16)
    body+=text(1030,674,'GP1 → GPIO3',16)
    body+=text(828,705,'GP21 → GPIO27',16)
    body+=text(828,761,'J1 names the connector.',17,weight=700)
    body+=text(828,787,'Use the pin-1 mark to orient it.',16)
    body+=text(38,869,'Top view of the header · match physical pin 1 before connecting · disconnect all power before rewiring',17,'#536b7d')
    return svg(1280,910,'Physical pins and BCM GPIO numbers','40 physical positions, the first 26 used by Gertboard J1, and the GPIO17 example.',body)


class Canvas:
    def __init__(self):self.items={};self.count=0
    def configure(self,**kw):pass
    def bind(self,*args,**kw):pass
    def create(self,kind,coordinates,kw):
        self.count+=1;self.items[self.count]={'kind':kind,'xy':coordinates,**kw};return self.count
    def create_rectangle(self,*xy,**kw):return self.create('rect',xy,kw)
    def create_oval(self,*xy,**kw):return self.create('ellipse',xy,kw)
    def create_line(self,*xy,**kw):return self.create('line',xy,kw)
    def create_text(self,*xy,**kw):return self.create('text',xy,kw)
    def itemconfigure(self,item,**kw):self.items[item].update(kw)


def board_map():
    set_language('en');canvas=Canvas();GertboardDiagram(canvas,lambda key:None)
    body='<rect width="720" height="618" fill="#f3f6fa"/>'
    for item in canvas.items.values():
        kind=item['kind'];xy=item['xy'];fill=item.get('fill') or 'none'
        stroke=item.get('outline') or 'none';width=item.get('width',1)
        if kind=='rect':
            x1,y1,x2,y2=xy;body+=f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        elif kind=='ellipse':
            x1,y1,x2,y2=xy;body+=f'<ellipse cx="{(x1+x2)/2}" cy="{(y1+y2)/2}" rx="{(x2-x1)/2}" ry="{(y2-y1)/2}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>'
        elif kind=='line':
            x1,y1,x2,y2=xy;body+=f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{fill}" stroke-width="{width}"/>'
        else:
            x,y=xy;_,size,*weight=item.get('font',('',9))
            value=item['text']
            if value.startswith('Click an area'):
                value='Static board map · open the in-app atlas for interactive details'
            lines=value.split('\n')
            anchor={'w':'start','e':'end'}.get(item.get('anchor'),'middle')
            for index,line in enumerate(lines):
                body+=text(x,y+(index-(len(lines)-1)/2)*size*1.5+size*.45,line,size*1.25,fill,700 if 'bold' in weight else 400,anchor)
    return svg(720,618,'Gertboard functional areas','Static schematic from the same board model used by the optional in-app atlas. Connectors are not live measurements.',body)


if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    for name,contents in [('project-banner.svg',banner()),('pin-orientation.svg',pinout()),('gertboard-map.svg',board_map())]:
        (OUT/name).write_text(contents,encoding='utf-8');print(name)
