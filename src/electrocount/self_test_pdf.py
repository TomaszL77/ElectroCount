"""Tiny built-in vector/text fixture. No test framework or ReportLab dependency."""
from pathlib import Path


def create_pdf(path):
    lines=[]
    for row in range(3):
        for col in range(4):
            x,y=40+col*105,440-row*105
            lines.append(f'0 0 1 RG 1 w {x} {y} 24 12 re S {x} {y} m {x+24} {y+12} l S '
                         f'{x+24} {y} m {x} {y+12} l S 0 g BT /F1 9 Tf {x+29} {y+3} Td (EC12) Tj ET')
    drawing='\n'.join(lines).encode('ascii')
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 500] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length '+str(len(drawing)).encode()+b' >>\nstream\n'+drawing+b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    data=bytearray(b'%PDF-1.4\n');offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
    start=len(data);data.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    data.extend(b''.join(f'{n:010} 00000 n \n'.encode() for n in offsets[1:]))
    data.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    Path(path).write_bytes(data)
