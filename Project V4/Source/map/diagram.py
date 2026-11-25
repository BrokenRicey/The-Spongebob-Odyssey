"""Native, offline geographic canvas. GIS and electrical branches stay distinct."""
import json
import math
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPainterPath, QFont
from PySide6.QtWidgets import QWidget, QToolTip
from simulation.study import ROOT

DARK = dict(bg='#081722', panel='#102330', border='#263f4e', text='#e6f2fc', muted='#8daabd', accent='#2ec8ed',
            geo='#304d5c', grid='#152c39', line='#53cad2', facility='#ffbe61', water='#102f44')
LIGHT = dict(bg='#edf0e9', panel='#ffffff', border='#d5ddd9', text='#1c293b', muted='#647582', accent='#aa5527',
             geo='#b4c5bb', grid='#dce4db', line='#008e96', facility='#ac5526', water='#c9e1ec')


class GridMap(QWidget):
    selected = Signal(str, str)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(240, 210)
        self.setMouseTracking(True)
        self.palette_colors = DARK
        self.model = None
        self.result = None
        self.baseline = None
        self.mode = 'Baseline'
        self.active = ('loads', 'DC_01')
        self.zoom = 1.
        self.pan = QPointF()
        self.drag = None
        self.hit = []
        self.show_gis = True
        self.show_directory = True
        raw = json.loads((ROOT / 'data/github_houston/houston_lines.geojson').read_text(encoding='utf-8'))
        self.routes = []
        for f in raw['features']:
            g = f['geometry']
            self.routes.extend([g['coordinates']] if g['type'] == 'LineString' else g['coordinates'])
        raw = json.loads((ROOT / 'data/github_houston/data_centers.geojson').read_text(encoding='utf-8'))
        self.directory = raw['features']

    def project(self, lon, lat):
        # Fixed Houston extent; uniform aspect ratio in approximate local projection.
        scale = min(self.width() / 1.07, self.height() / .78) * self.zoom
        return QPointF(self.width()/2 + (lon + 95.38)*.87*scale + self.pan.x(),
                       self.height()/2 - (lat - 29.79)*scale + self.pan.y())

    def point(self, bus):
        return self.project(bus['lon'], bus['lat'])

    def fit(self):
        self.zoom = 1.
        self.pan = QPointF()
        self.update()

    def zoom_by(self, factor):
        self.zoom = max(.65, min(8, self.zoom * factor))
        self.update()

    def wheelEvent(self, event):
        self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1/1.15)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag = event.position()
            self.start = event.position()

    def mouseMoveEvent(self, event):
        if self.drag is not None:
            self.pan += event.position()-self.drag
            self.drag = event.position()
            self.update()
        else:
            for rect, section, key, tip in reversed(self.hit):
                if rect.contains(event.position()):
                    self.setCursor(Qt.PointingHandCursor)
                    QToolTip.showText(event.globalPosition().toPoint(), tip, self)
                    return
            self.setCursor(Qt.OpenHandCursor)
            QToolTip.hideText()

    def mouseReleaseEvent(self, event):
        if self.drag is not None and (event.position()-self.start).manhattanLength() < 5:
            for rect, section, key, tip in reversed(self.hit):
                if rect.contains(event.position()):
                    self.active = (section, key)
                    self.selected.emit(section, key)
                    break
        self.drag = None
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.palette_colors
        p.fillRect(self.rect(), QColor(c['bg']))
        p.setPen(QPen(QColor(c['grid']), 1))
        for lon in [-95.9 + i*.1 for i in range(13)]:
            p.drawLine(self.project(lon,29.3),self.project(lon,30.3))
        for lat in [29.3+i*.1 for i in range(11)]:
            p.drawLine(self.project(-96,lat),self.project(-94.7,lat))
        # Geographic orientation, not a downloaded street basemap.
        bay = QPainterPath()
        coastline = [(-94.98,29.75),(-95.04,29.67),(-94.99,29.60),(-95.02,29.53),(-94.92,29.46),(-94.7,29.4),(-94.7,29.8)]
        bay.moveTo(self.project(*coastline[0]))
        for pt in coastline[1:]: bay.lineTo(self.project(*pt))
        bay.closeSubpath()
        p.fillPath(bay, QColor(c['water']))
        if self.show_gis:
            p.setPen(QPen(QColor(c['geo']), 1))
            for route in self.routes:
                if len(route)<2: continue
                path = QPainterPath(self.project(*route[0][:2]))
                for pt in route[1:]: path.lineTo(self.project(*pt[:2]))
                p.drawPath(path)
        p.setFont(QFont('Segoe UI', 10))
        for name,lon,lat in [('HOUSTON',-95.369,29.755),('The Woodlands',-95.47,30.16),('Cypress',-95.70,29.97),('Humble',-95.26,30.0),('Katy',-95.81,29.79),('Sugar Land',-95.64,29.59),('Pearland',-95.38,29.49),('Baytown',-94.96,29.79),('Galveston Bay',-94.98,29.47)]:
            pt = self.project(lon,lat)
            p.setPen(QColor(c['muted']))
            p.drawText(pt, name)
        self.hit = []
        if self.show_directory:
            p.setPen(QPen(QColor('#ab83d1'),1.5))
            p.setBrush(Qt.NoBrush)
            for i,f in enumerate(self.directory):
                pt=self.project(*f['geometry']['coordinates'][:2])
                p.drawEllipse(pt,3.5,3.5)
                props=f['properties']
                tip='Directory location (not modeled)\n'+str(props.get('name',props.get('names','Approximate address')))
                self.hit.append((QRectF(pt.x()-6,pt.y()-6,12,12),'directory',str(i),tip))
        if not self.model:
            p.end(); return
        buses={b['id']:b for b in self.model['buses']}
        result=self.result or {}
        violation_ids={v['id'] for v in result.get('violations',[])}
        for section, items in [('lines',self.model['lines']),('transformers',self.model.get('transformers',[]))]:
            for line in items:
                a=self.point(buses[line.get('from_bus',line.get('hv_bus'))])
                b=self.point(buses[line.get('to_bus',line.get('lv_bus'))])
                row=result.get(section,{}).get(line['id'],{})
                off=row.get('in_service') is False
                color='#fc5863' if line['id'] in violation_ids else c['line']
                if section=='transformers': color=c['facility']
                if off: color=c['muted']
                if self.mode=='Change' and row and self.baseline:
                    old=self.baseline.get(section,{}).get(line['id'],{}).get('loading_percent')
                    new=row.get('loading_percent')
                    if old is not None and new is not None and not off: color='#f3a34f' if new>old+.01 else '#51b9c8'
                pen=QPen(QColor(color),3 if self.active==(section,line['id']) else 1.9)
                if off: pen.setStyle(Qt.DashLine)
                p.setPen(pen); p.drawLine(a,b)
                mid=(a+b)/2
                p.setBrush(QColor(color))
                p.drawEllipse(mid,3,3)
                if off:
                    p.setFont(QFont('Segoe UI',9,QFont.Bold)); p.drawText(mid+QPointF(6,-5),line['id']+' OFF')
                elif row.get('p_from_mw') is not None:
                    direction=1 if row['p_from_mw']>=0 else -1
                    angle=math.atan2(b.y()-a.y(),b.x()-a.x())+(0 if direction==1 else math.pi)
                    path=QPainterPath(mid)
                    path.lineTo(mid+QPointF(-7*math.cos(angle-.5),-7*math.sin(angle-.5)))
                    path.lineTo(mid+QPointF(-7*math.cos(angle+.5),-7*math.sin(angle+.5)))
                    path.closeSubpath();p.fillPath(path,QColor(color))
                self.hit.append((QRectF(mid.x()-9,mid.y()-9,18,18),section,line['id'],line['id']+' · modeled branch'))
        for bus in self.model['buses']:
            pt=self.point(bus)
            color='#fc5863' if bus['id'] in violation_ids else c['accent']
            p.setPen(QPen(QColor(color),2)); p.setBrush(QColor(c['panel']))
            if self.active==('buses',bus['id']):p.drawEllipse(pt,12,12)
            if bus['vn_kv']==345:p.drawRect(QRectF(pt.x()-6,pt.y()-6,12,12))
            else:p.drawEllipse(pt,5,5)
            p.setPen(QColor(c['text']));p.setFont(QFont('Segoe UI',8))
            if self.width()>760 or self.zoom>1.3 or self.active==('buses',bus['id']):
                p.drawText(pt+QPointF(8,15),bus['id'].replace('BUS_','B'))
            self.hit.append((QRectF(pt.x()-10,pt.y()-10,20,20),'buses',bus['id'],f"{bus['id']} · {bus['vn_kv']} kV\n{bus.get('substation_name','')}\nModeled bus; assumed electrical parameters"))
        for i,load in enumerate(self.model['loads']):
            buspt=self.point(buses[load['bus_id']])
            angle=(i%4)*math.pi/2+.45
            offset=QPointF(29*math.cos(angle),29*math.sin(angle))
            pt=buspt+offset
            p.setPen(QPen(QColor(c['facility']),1,Qt.DashLine));p.drawLine(buspt,pt)
            p.setPen(QPen(QColor(c['facility']),1.5));p.setBrush(QColor(c['panel']))
            p.drawRoundedRect(QRectF(pt.x()-7,pt.y()-10,14,19),2,2)
            if self.active==('loads',load['id']):p.drawEllipse(pt,17,17)
            for dx in [-3,2]:
                for dy in [-6,-1,4]:p.fillRect(QRectF(pt.x()+dx,pt.y()+dy,2,2),QColor(c['facility']))
            p.setPen(QColor(c['facility']));p.setFont(QFont('Segoe UI',8,QFont.Bold))
            if self.width()>760 or self.zoom>1.3 or self.active==('loads',load['id']):
                p.drawText(pt+QPointF(10,-4),load['id'].replace('DC_','DC '))
            self.hit.append((QRectF(pt.x()-12,pt.y()-14,24,28),'loads',load['id'],f"{load['id']} · synthetic study load\nConnection: {load['bus_id']} (assumed)"))
        p.setFont(QFont('Segoe UI',8))
        p.setPen(QColor(c['muted']))
        p.drawText(16,self.height()-16,'OFFLINE GEOGRAPHIC VIEW  ·  Drag to pan / scroll to zoom')
        p.drawText(self.width()-30,25,'N ↑')
        p.end()


class SweepChart(QWidget):
    def __init__(self):
        super().__init__();self.points=[];self.colors=DARK;self.setMinimumHeight(170)

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        c=self.colors;p.fillRect(self.rect(),QColor(c['panel']));p.setPen(QColor(c['muted']))
        p.setFont(QFont('Segoe UI',10))
        if not self.points:
            p.drawText(self.rect(),Qt.AlignCenter,'Run an AI training sweep to compare 0–150% demand.');p.end();return
        r=QRectF(65,30,self.width()-105,self.height()-75)
        values=[x['result'].get('totals',{}).get('min_voltage_pu') for x in self.points]
        finite=[v for v in values if v is not None]
        if not finite:p.drawText(self.rect(),Qt.AlignCenter,'No converged sweep points');p.end();return
        lo=min(.94,min(finite)-.01);hi=max(1.03,max(finite)+.01)
        y=lambda v:r.bottom()-(v-lo)/(hi-lo)*r.height()
        p.drawRect(r);p.drawText(12,20,'Min voltage (pu)')
        p.drawText(int(r.left()),self.height()-10,'0%');p.drawText(int(r.right()-25),self.height()-10,'150% demand')
        for v in [lo,.95,hi]:
            p.setPen(QPen(QColor('#fc5863' if v==.95 else c['border']),1,Qt.DashLine));p.drawLine(QPointF(r.left(),y(v)),QPointF(r.right(),y(v)))
            p.setPen(QColor(c['muted']));p.drawText(12,int(y(v))+4,f'{v:.3f}')
        p.setPen(QPen(QColor(c['accent']),2.5))
        previous=None
        for point,v in zip(self.points,values):
            if v is None:previous=None;continue
            pt=QPointF(r.left()+point['scale']/1.5*r.width(),y(v))
            if previous is not None:p.drawLine(previous,pt)
            p.drawEllipse(pt,3,3);previous=pt
        p.end()
