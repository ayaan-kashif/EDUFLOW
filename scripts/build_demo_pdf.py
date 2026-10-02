"""Build the original offline source fixture (no external curriculum content)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from app.demo import TOPICS

path = Path(__file__).resolve().parent.parent / 'app/static/demo-biology.pdf'
pdf = canvas.Canvas(str(path), pagesize=(595,842))
pdf.setTitle('EduFlow - Original Biology Demo Notes')
pdf.setAuthor('EduFlow demo fixtures')
for i, (label, text, _, _) in enumerate(TOPICS):
    pdf.setFillColor(HexColor('#f5f4ee'))
    pdf.rect(0,0,595,842,fill=1,stroke=0)
    pdf.setFillColor(HexColor('#394e39'))
    pdf.setFont('Helvetica',10)
    pdf.drawString(48,790,'EDUFLOW / ORIGINAL TEACHING NOTES')
    pdf.setStrokeColor(HexColor('#dde1d5'))
    pdf.line(48,773,547,773)
    pdf.setFont('Times-Roman',30)
    pdf.drawString(48,707,label)
    pdf.setFont('Helvetica',10)
    pdf.drawString(48,677,f'DEMO.BIO.{i+1:02d}  |  Synthetic classroom example')
    pdf.setFillColor(HexColor('#202a24'))
    pdf.setFont('Helvetica',15)
    y = 606
    for line in simpleSplit(text,'Helvetica',15,490):
        pdf.drawString(48,y,line)
        y -= 25
    pdf.setFillColor(HexColor('#657065'))
    pdf.setFont('Helvetica',10)
    for j,line in enumerate(simpleSplit('These original notes demonstrate source attribution. They are not an official examination syllabus and have not been independently reviewed for teaching use.','Helvetica',10,490)):
        pdf.drawString(48,160-j*15,line)
    pdf.line(48,90,547,90)
    pdf.drawString(48,68,'No student data. Evidence before eloquence.')
    pdf.drawRightString(547,68,str(i+1))
    pdf.showPage()
pdf.save()
print(path)
